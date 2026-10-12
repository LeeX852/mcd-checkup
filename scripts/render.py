#!/usr/bin/env python3
"""把 report.json 注入 app/index.html，产出一个可直接双击打开 / 直接托管的分发包。

    python scripts/render.py                                  # 用演示数据打包
    python scripts/render.py --data report.json --out out.html

产物是纯静态单文件：数据内联、零外部依赖、无网络请求，扔到 GitHub Pages 或本地磁盘都能看。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze import build_report          # noqa: E402

ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(ROOT, "app", "index.html")
SAMPLE_RAW = os.path.join(ROOT, "assets", "sample-raw.json")

DATA_TOKEN = "/*__CHECKUP_DATA__*/null"
SAMPLE_TOKEN = "/*__CHECKUP_SAMPLE__*/null"


def safe_json(obj) -> str:
    """内联进 <script> 的 JSON：避免 </script> 提前闭合标签。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build(data_obj, sample_obj, template_path=TEMPLATE) -> str:
    with open(template_path, encoding="utf-8") as fh:
        html = fh.read()
    if DATA_TOKEN not in html or SAMPLE_TOKEN not in html:
        raise SystemExit("模板缺少注入占位符，请检查 app/index.html")
    html = html.replace(DATA_TOKEN, "/*__CHECKUP_DATA__*/" + safe_json(data_obj), 1)
    html = html.replace(SAMPLE_TOKEN, "/*__CHECKUP_SAMPLE__*/" + safe_json(sample_obj), 1)
    return html


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打包单文件体检报告")
    parser.add_argument("--data", help="report.json 路径；缺省用演示数据")
    parser.add_argument("--out", default=os.path.join(ROOT, "preview.html"))
    parser.add_argument("--no-sample", action="store_true", help="不内嵌演示数据")
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

    html = build(data_obj, sample_obj)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("已生成 %s（%.1f KB）" % (args.out, os.path.getsize(args.out) / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
