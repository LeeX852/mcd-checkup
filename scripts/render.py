#!/usr/bin/env python3
"""把 report.json / card.json 注入模板，产出可直接双击打开 / 直接托管的分发包。

    python scripts/render.py                       # 演示数据 → preview.html + card.html
    python scripts/render.py --data report.json --out report.html

一次产出两个单文件：
    report.html  体检报告（数据内联）
    card.html    角色卡（独立卡片页，可导出 PNG）
两者是兄弟文件，报告页右上角的「角色卡」按钮直接跳到 card.html。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze import build_report          # noqa: E402
from card import build_card               # noqa: E402

ROOT = os.path.dirname(HERE)
REPORT_TEMPLATE = os.path.join(ROOT, "app", "index.html")
CARD_TEMPLATE = os.path.join(ROOT, "app", "card.html")
SAMPLE_RAW = os.path.join(ROOT, "assets", "sample-raw.json")

DATA_TOKEN = "/*__CHECKUP_DATA__*/null"
SAMPLE_TOKEN = "/*__CHECKUP_SAMPLE__*/null"
CARD_TOKEN = "/*__CARD_DATA__*/null"


def safe_json(obj) -> str:
    """内联进 <script> 的 JSON：避免 </script> 提前闭合标签。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build(data_obj, sample_obj, template_path=REPORT_TEMPLATE) -> str:
    with open(template_path, encoding="utf-8") as fh:
        html = fh.read()
    if DATA_TOKEN not in html or SAMPLE_TOKEN not in html:
        raise SystemExit("报告模板缺少注入占位符，请检查 app/index.html")
    html = html.replace(DATA_TOKEN, "/*__CHECKUP_DATA__*/" + safe_json(data_obj), 1)
    html = html.replace(SAMPLE_TOKEN, "/*__CHECKUP_SAMPLE__*/" + safe_json(sample_obj), 1)
    return html


def build_card_html(card_obj, template_path=CARD_TEMPLATE) -> str:
    with open(template_path, encoding="utf-8") as fh:
        html = fh.read()
    if CARD_TOKEN not in html:
        raise SystemExit("卡片模板缺少注入占位符，请检查 app/card.html")
    return html.replace(CARD_TOKEN, "/*__CARD_DATA__*/" + safe_json(card_obj), 1)


def inline_portrait(payload):
    """把当前画像对应的立绘以 data URI 内联，保证产物仍是单文件、可离线打开。"""
    p = payload.get("persona") or {}
    rel = p.get("portrait")
    if not rel or str(rel).startswith("data:"):
        return payload
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        p.pop("portrait", None)
        return payload
    with open(path, "rb") as fh:
        p["portrait"] = "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    return payload


def _write(path: str, content: str, label: str) -> None:
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("已生成 %s（%s，%.1f KB）" % (path, label, os.path.getsize(path) / 1024))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打包单文件体检报告与角色卡")
    parser.add_argument("--data", help="report.json 路径；缺省用演示数据")
    parser.add_argument("--out", default=os.path.join(ROOT, "preview.html"))
    parser.add_argument("--card-out", default=os.path.join(ROOT, "card.html"),
                        help="角色卡输出路径，默认 card.html")
    parser.add_argument("--no-sample", action="store_true", help="不内嵌演示数据")
    parser.add_argument("--no-card", action="store_true", help="不生成角色卡页")
    args = parser.parse_args(argv)

    sample_obj = None
    if not args.no_sample:
        with open(SAMPLE_RAW, encoding="utf-8") as fh:
            sample_obj = build_report(json.load(fh), mode="sample")

    if args.data:
        with open(args.data, encoding="utf-8") as fh:
            data_obj = json.load(fh)
    else:
        data_obj = sample_obj

    _write(args.out, build(data_obj, sample_obj), "报告")

    if not args.no_card:
        payload = inline_portrait(build_card(data_obj))
        _write(args.card_out, build_card_html(payload), "角色卡")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
