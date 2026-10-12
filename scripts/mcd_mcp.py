"""麦当劳 MCP Server 的极简 JSON-RPC 客户端（Streamable HTTP）。

只依赖 Python 标准库，不引入 requests / mcp sdk，保证 `python scripts/checkup.py`
在任何装了 Python 3.9+ 的机器上都能直接跑。

协议流程：
    initialize -> notifications/initialized -> tools/call ...

Token 只从环境变量 MCD_MCP_TOKEN 读取，永远不会落盘、不会进 git。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"

# 只读工具清单：体检报告只做查询，绝不触碰下单 / 领券 / 抽奖等写操作。
READ_ONLY_TOOLS = frozenset(
    {
        "order-list",
        "mall-order-list",
        "query-my-account",
        "query-my-coupons",
        "available-coupons",
        "list-nutrition-foods",
        "query-lottery-info",
        "query-my-prizes",
        "campaign-calendar",
        "now-time-info",
    }
)


class McpError(RuntimeError):
    """MCP 调用失败。"""


class McdMcp:
    def __init__(self, token: Optional[str] = None, url: Optional[str] = None,
                 timeout: int = 30, retries: int = 3):
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "").strip()
        self.url = (url or os.environ.get("MCD_MCP_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.retries = max(1, retries)
        self.session_id: Optional[str] = None
        self._id = 0
        if not self.token:
            raise McpError(
                "缺少 MCP Token。请先设置环境变量 MCD_MCP_TOKEN，"
                "或直接在 ~/.workbuddy/mcp.json 里配好 mcd-mcp 连接器。"
            )

    # ---------------------------------------------------------------- transport

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.token,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")

        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    sid = resp.headers.get("Mcp-Session-Id")
                break
            except urllib.error.HTTPError as exc:  # noqa: PERF203
                detail = exc.read().decode("utf-8", "replace")[:300]
                if exc.code == 401:
                    raise McpError("MCP Token 无效或已过期（401）：" + detail) from exc
                if exc.code == 429:
                    raise McpError("触发限流（429），请降低调用频率后重试：" + detail) from exc
                raise McpError("HTTP %s：%s" % (exc.code, detail)) from exc
            except (urllib.error.URLError, OSError) as exc:
                # TLS 握手偶发被中断 / 连接被重置，退避后重试；不重试 4xx 类业务错误。
                last_error = exc
                if attempt >= self.retries:
                    raise McpError("网络请求失败：%s" % getattr(exc, "reason", exc)) from exc
                time.sleep(0.6 * attempt)
        else:  # pragma: no cover - 循环只会通过 break 或 raise 退出
            raise McpError("网络请求失败：%s" % last_error)

        if sid:
            self.session_id = sid
        if not raw.strip():
            # 通知（notification）按协议不回 body，通常是 202 空响应，属正常情况。
            return {}
        return _parse_payload(raw)

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None,
             notify: bool = False) -> Dict[str, Any]:
        self._id += 1
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notify:
            payload["id"] = self._id
        return self._post(payload)

    # ---------------------------------------------------------------- lifecycle

    def initialize(self) -> Dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-checkup", "version": "1.0.0"},
            },
        )["result"]
        self._rpc("notifications/initialized", {}, notify=True)
        return result

    def list_tools(self) -> list:
        return self._rpc("tools/list", {})["result"].get("tools", [])

    # ---------------------------------------------------------------- tool call

    def call(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用指定工具，返回 dict：{"data": ..., "text": ..., "isError": bool}。"""
        if name not in READ_ONLY_TOOLS:
            raise McpError("拒绝调用非只读工具：%s（体检报告只做查询）" % name)
        envelope = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        result = envelope.get("result") or {}
        if result.get("isError"):
            piece = (result.get("content") or [{}])[0].get("text", "")
            raise McpError("工具 %s 返回错误：%s" % (name, piece[:200]))
        return _unwrap(result)


# --------------------------------------------------------------------- helpers


def _parse_payload(raw: str) -> Dict[str, Any]:
    """服务端可能直接返回 JSON，也可能返回 SSE（过了和不稳定两种情况都得接住）。"""
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        obj = json.loads(raw)
    else:
        obj = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                obj = json.loads(line[5:].strip())
                break
        if obj is None:
            raise McpError("无法解析 MCP 响应：" + raw[:200])
    if "error" in obj:
        err = obj["error"]
        raise McpError("MCP 错误 %s：%s" % (err.get("code"), err.get("message")))
    if "result" not in obj:
        raise McpError("MCP 响应缺少 result 字段")
    return obj


def _unwrap(result: Dict[str, Any]) -> Dict[str, Any]:
    """把 tools/call 结果归一化。

    麦当劳 MCP 每个工具都会同时给：
      1) structuredContent：已经结构化的 dict；
      2) content[0].text：给 LLM 看的长文本，尾部还有一段 `## Original Response` JSON。
    优先取 structuredContent，退化时从文本里抠 JSON，最后兜底返回纯文本。
    """
    text = ""
    for piece in result.get("content") or []:
        if piece.get("type") == "text":
            text += piece.get("text", "")

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return {"data": structured.get("data"), "text": text, "isError": False}

    extracted = _extract_json_tail(text)
    if extracted is not None:
        return {"data": extracted.get("data"), "text": text, "isError": False}
    return {"data": None, "text": text, "isError": False}


def _extract_json_tail(text: str) -> Optional[Dict[str, Any]]:
    """从 `## Original Response` 之后截取第一段 JSON。"""
    marker = "## Original Response"
    idx = text.rfind(marker)
    if idx == -1:
        return None
    chunk = text[idx + len(marker):].lstrip()
    chunk = chunk.lstrip("\r\n")
    depth = 0
    for pos, ch in enumerate(chunk):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(chunk[: pos + 1])
                except json.JSONDecodeError:
                    return None
    return None
