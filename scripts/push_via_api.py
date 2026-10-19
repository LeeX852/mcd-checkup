#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 GitHub API 推送本地提交（绕过被拦的 github.com）。

本机代理只放行 api.github.com，`git push` 会在 TLS 阶段卡死。
这个脚本把本地尚未推送的提交**逐个重放**到远端，保留提交历史与 tag：

    git diff-tree 找出每个提交的变更 → 上传新 blob
      → 用 git ls-tree 的完整 tree 建树 → 建 commit
      → 全部成功后再更新 refs/heads/main，最后补 tag

用法：
    python scripts/push_via_api.py            # 推送 main 与本地 tag
    python scripts/push_via_api.py --dry-run  # 只打印将要做什么
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
OWNER, REPO = "LeeX852", "mcd-checkup"
BRANCH = "main"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ 基础


def token() -> str:
    return subprocess.check_output(["gh", "auth", "token"]).decode().strip()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def text(*args: str) -> str:
    return git(*args).decode("utf-8").strip()


def api(method: str, path: str, body=None):
    """带退避重试的 GitHub API 调用。代理会偶发重置连接，必须重试。"""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    last = None
    for attempt in range(5):
        req = urllib.request.Request(
            API + path, data=data, method=method,
            headers={
                "Authorization": "Bearer " + token(),
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError("HTTP %s %s：%s" % (exc.code, path, detail)) from exc
        except Exception as exc:  # 代理重置 / TLS 抖动
            last = exc
            if attempt == 4:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("API 调用重试 5 次仍失败：%s %s -> %s" % (method, path, last))


# ------------------------------------------------------------------ git 读取


def ls_tree(sha: str):
    """递归读取某个提交的完整文件列表（只有 blob）。"""
    out = git("ls-tree", "-r", "-z", sha)
    entries = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, _typ, blob = meta.decode("utf-8").split()
        entries.append({
            "path": path.decode("utf-8"),
            "mode": mode,
            "type": "blob",
            "sha": blob,
        })
    return entries


def changed_blobs(parent: str, commit: str):
    """新增/修改的文件路径（删除项不需要上传，建树时自然消失）。"""
    out = git("diff-tree", "-r", "--no-commit-id", "--name-status", "-z", parent, commit)
    toks = [t.decode("utf-8") for t in out.split(b"\0") if t]
    paths, i = [], 0
    while i < len(toks):
        status = toks[i]
        if status[:1] in ("R", "C"):
            paths.append(toks[i + 2])
            i += 3
        else:
            if status[:1] in ("A", "M", "T"):
                paths.append(toks[i + 1])
            i += 2
    return paths


def find_local_by_tree(tree_sha: str):
    """远端历史被 API 重写过时，按 tree 找到内容等价的本地提交作为基准。"""
    for line in text("log", "--all", "--format=%H %T").splitlines():
        sha, tree = line.split()
        if tree == tree_sha:
            return sha
    return None


def commit_meta(sha: str):
    raw = git("show", "-s", "--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B", sha)
    parts = raw.split(b"\0")
    an, ae, ad, cn, ce, cd = [p.decode("utf-8").strip() for p in parts[:6]]
    msg = b"\0".join(parts[6:]).decode("utf-8").strip() + "\n"
    return {
        "message": msg,
        "author": {"name": an, "email": ae, "date": ad},
        "committer": {"name": cn, "email": ce, "date": cd},
    }


# ------------------------------------------------------------------ 推送


def main() -> int:
    dry = "--dry-run" in sys.argv

    remote = api("GET", "/repos/%s/%s/git/ref/heads/%s" % (OWNER, REPO, BRANCH))
    remote_sha = remote["object"]["sha"]
    remote_tree = api("GET", "/repos/%s/%s/git/commits/%s" % (OWNER, REPO, remote_sha))["tree"]["sha"]
    head = text("rev-parse", "HEAD")

    if remote_sha == head:
        print("远端已是最新：%s" % head[:10])
        sync_tags({head: remote_sha}, head, remote_sha)
        return 0

    probe = subprocess.run(["git", "merge-base", "--is-ancestor", remote_sha, head],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode == 0:
        base_local = remote_sha
    else:
        # 远端提交不在本地历史（历史上用 API 推过，SHA 不同但内容可能一致）
        base_local = find_local_by_tree(remote_tree)
        if not base_local:
            print("远端内容与本地任何提交都不一致，拒绝推进。")
            print("  remote %s tree=%s" % (remote_sha[:10], remote_tree[:10]))
            return 2
        print("远端提交由 API 重写，内容对齐到本地 %s" % base_local[:10])

    commits = text("rev-list", "--reverse", "%s..%s" % (base_local, head)).splitlines()
    print("远端 %s → 本地 %s，待推送 %d 个提交" % (remote_sha[:10], head[:10], len(commits)))
    if dry:
        for c in commits:
            print("  " + text("log", "-1", "--format=%h %s", c))
        return 0

    mapping = {base_local: remote_sha}
    parent_remote = remote_sha

    for local in commits:
        subject = text("log", "-1", "--format=%h %s", local)
        print("\n→ " + subject)

        # 1) 上传变更文件
        try:
            local_parent = text("rev-parse", local + "^")
        except subprocess.CalledProcessError:
            local_parent = local
        uploaded = 0
        for path in changed_blobs(local_parent, local):
            try:
                blob = git("rev-parse", "%s:%s" % (local, path))
                content = git("cat-file", "-p", blob.decode().strip())
            except subprocess.CalledProcessError:
                continue
            if not content and path.endswith("/"):
                continue
            api("POST", "/repos/%s/%s/git/blobs" % (OWNER, REPO), {
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            })
            uploaded += 1
        print("   blob %d 个" % uploaded)

        # 2) 建树（完整树，避免 base_tree 与远端不一致）
        entries = ls_tree(local)
        tree = api("POST", "/repos/%s/%s/git/trees" % (OWNER, REPO), {"tree": entries})
        print("   tree %s（%d 项）" % (tree["sha"][:10], len(entries)))

        # 3) 建提交
        meta = commit_meta(local)
        commit = api("POST", "/repos/%s/%s/git/commits" % (OWNER, REPO), {
            "message": meta["message"],
            "tree": tree["sha"],
            "parents": [parent_remote],
            "author": meta["author"],
            "committer": meta["committer"],
        })
        print("   commit %s" % commit["sha"][:10])

        mapping[local] = commit["sha"]
        parent_remote = commit["sha"]

    # 4) 更新分支
    api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (OWNER, REPO, BRANCH),
        {"sha": parent_remote, "force": False})
    print("\n分支 %s → %s" % (BRANCH, parent_remote[:10]))

    # 5) 补 tag
    sync_tags(mapping, head, parent_remote)

    print("\n完成：https://github.com/%s/%s" % (OWNER, REPO))
    return 0


def sync_tags(mapping, local_head: str, remote_head: str) -> None:
    """把本地 tag 映射到远端提交；远端已有的 tag 不覆盖。"""
    existing = {}
    try:
        refs = api("GET", "/repos/%s/%s/git/refs/tags" % (OWNER, REPO))
        existing = {r["ref"].split("/")[-1] for r in refs}
    except RuntimeError:
        pass

    for name in text("tag", "-l").splitlines():
        if name in existing:
            print("   skip tag %s（远端已存在）" % name)
            continue
        target = text("rev-list", "-n", "1", name)
        sha = mapping.get(target)
        if not sha:
            print("   skip tag %s（指向未推送的提交）" % name)
            continue
        api("POST", "/repos/%s/%s/git/refs" % (OWNER, REPO),
            {"ref": "refs/tags/" + name, "sha": sha})
        print("   tag %s → %s" % (name, sha[:10]))


if __name__ == "__main__":
    raise SystemExit(main())
