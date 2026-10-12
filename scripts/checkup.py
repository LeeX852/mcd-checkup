#!/usr/bin/env python3
"""麦麦体检报告 · 主流程。

    python scripts/checkup.py                     # 调 MCP 抓数 -> 生成 report.json
    python scripts/checkup.py --sample            # 用内置演示数据（无 Token 也能跑）
    python scripts/checkup.py --from-raw raw.json # 从已抓好的原始数据生成
    python scripts/checkup.py --dump-raw          # 同时落盘原始抓取结果，便于排查

只调用只读工具，不会产生下单、领券、抽奖等任何写操作。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze import build_report                       # noqa: E402
from mcd_mcp import McdMcp, READ_ONLY_TOOLS            # noqa: E402


def fetch_raw(mcp: McdMcp) -> dict:
    """依次调用只读工具，任何单个失败都不影响整体出报告。"""
    raw = {}
    for name in sorted(READ_ONLY_TOOLS):
        try:
            raw[name] = mcp.call(name)
        except Exception as exc:  # noqa: BLE001
            raw[name] = {"data": None, "text": "", "isError": True, "error": str(exc)}
            print("  [warn] %s 失败：%s" % (name, exc), file=sys.stderr)
    return raw


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="麦当劳消费体检报告生成器")
    parser.add_argument("--out", default="report.json", help="输出报告路径，默认 report.json")
    parser.add_argument("--sample", action="store_true",
                        help="使用内置演示数据，不需要 MCP Token")
    parser.add_argument("--from-raw", help="从已抓好的原始 JSON 生成，跳过 MCP 调用")
    parser.add_argument("--dump-raw", action="store_true", help="同时保存原始抓取结果")
    parser.add_argument("--quiet", action="store_true", help="不打印摘要")
    args = parser.parse_args(argv)

    if args.from_raw:
        with open(args.from_raw, encoding="utf-8") as fh:
            raw = json.load(fh)
        mode = "offline"
        print("已从 %s 载入原始数据" % args.from_raw)
    elif args.sample:
        sample = os.path.join(HERE, "..", "assets", "sample-raw.json")
        with open(sample, encoding="utf-8") as fh:
            raw = json.load(fh)
        mode = "sample"
        print("已载入内置演示数据（assets/sample-raw.json）")
    else:
        print("正在连接麦当劳 MCP Server ...")
        mcp = McdMcp()
        info = mcp.initialize()
        print("已连接：%s %s" % (info.get("serverInfo", {}).get("name"),
                                  info.get("serverInfo", {}).get("version")))
        raw = fetch_raw(mcp)
        mode = "live"
        if args.dump_raw:
            raw_path = os.path.splitext(args.out)[0] + ".raw.json"
            os.makedirs(os.path.dirname(os.path.abspath(raw_path)), exist_ok=True)
            with open(raw_path, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, ensure_ascii=False)
            print("原始数据已保存：%s" % raw_path)

    report = build_report(raw, mode=mode)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        _print_summary(report, args.out)
    return 0


def _print_summary(report: dict, out_path: str) -> None:
    overview = report["overview"]
    nutrition = report["nutrition"]
    print()
    print("========== 麦麦体检报告 ==========")
    print("模式           %s" % report["meta"]["mode"])
    print("订单数         %d" % overview["orderCount"])
    print("累计消费       ¥%.2f" % overview["totalSpend"])
    print("客单价         ¥%.2f" % overview["avgTicket"])
    print("累计热量       %.0f kcal ≈ %.1f 个巨无霸"
          % (nutrition["energyKcal"], nutrition["bigMacEquivalent"]))
    print("可用积分       %.1f" % report["points"]["available"])
    print("结论卡片       %d 张" % len(report["verdicts"]))
    print("已写入         %s" % os.path.abspath(out_path))
    print("==================================")


if __name__ == "__main__":
    raise SystemExit(main())
