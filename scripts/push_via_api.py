#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绕过被代理拦死的 github.com，纯走 api.github.com 推送提交与 tag。

用法：python push_via_api.py <commit message>
依赖 gh 已登录（用 `gh auth token` 取令牌，不落盘）。
"""
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "README.md",
    "scripts/make_poster.py",
    "scripts/push_via_api.py",
    "screenshots/Premium_3D_product_marketing_i_2026-10-12T13-56-40.png",
    "screenshots/hero-clean.png",
    "screenshots/og-banner.png",
    "screenshots/poster.png",
]


def token():
    return subprocess.check_output(["gh", "auth", "token"]).decode().strip()


def api(method, path, body=None):
    """带退避重试的 GitHub API 调用。本机代理会偶发重置连接，必须重试。"""
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
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError("HTTP %s %s：%s" % (exc.code, path, detail)) from exc
        except Exception as exc:  # 代理重置 / TLS 抖动，退避后重试
            last = exc
            if attempt == 4:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("API 调用重试 5 次仍失败：%s %s -> %s" % (method, path, last))


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "chore: sync"

    ref = api("GET", "/repos/%s/%s/git/ref/heads/main" % (OWNER, REPO))
    parent = ref["object"]["sha"]
    base_tree = api("GET", "/repos/%s/%s/git/commits/%s" % (OWNER, REPO, parent))["tree"]["sha"]

    entries = []
    for rel in FILES:
        with open(os.path.join(ROOT, rel), "rb") as fh:
            raw = fh.read()
        blob = api("POST", "/repos/%s/%s/git/blobs" % (OWNER, REPO), {
            "content": base64.b64encode(raw).decode("ascii"),
            "encoding": "base64",
        })
        entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("blob  %-60s %8d B" % (rel, len(raw)))

    tree = api("POST", "/repos/%s/%s/git/trees" % (OWNER, REPO),
               {"base_tree": base_tree, "tree": entries})
    commit = api("POST", "/repos/%s/%s/git/commits" % (OWNER, REPO), {
        "message": msg, "tree": tree["sha"], "parents": [parent],
    })
    api("PATCH", "/repos/%s/%s/git/refs/heads/main" % (OWNER, REPO),
        {"sha": commit["sha"], "force": False})

    print("\ncommit %s -> main" % commit["sha"][:10])
    print("url    %s" % commit.get("html_url", ""))


if __name__ == "__main__":
    main()
