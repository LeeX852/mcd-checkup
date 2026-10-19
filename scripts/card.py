"""角色卡数据构建：report.json + persona → card.json。

一张卡 = 卡面类型（type）× 主题皮肤（theme）× 稀有度光晕（rarity）。
本模块只负责「说什么」，不负责「长什么样」；视觉全部由 app/card.html 用 Canvas 绘制。

    python scripts/card.py --data report.json --out card.json
    python scripts/card.py --sample --out card.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze import build_report          # noqa: E402
from persona import derive_persona        # noqa: E402

ROOT = os.path.dirname(HERE)
SAMPLE_RAW = os.path.join(ROOT, "assets", "sample-raw.json")

# ------------------------------------------------------------------ 主题皮肤
# pattern 是背景纹理类型：seeds（芝麻）/ stars（星点）/ rule（手账横线）
# / grid（赛博网格）/ foil（金箔斜光）
THEMES: List[Dict[str, Any]] = [
    {
        "key": "classic", "name": "经典红黄",
        "bg1": "#FFF8E6", "bg2": "#FFD98A", "surface": "#FFFDF7", "surface2": "#FFF3D8",
        "ink": "#221F1C", "ink2": "#5A5248", "ink3": "#94897B",
        "accent": "#DA291C", "accent2": "#FFC72C", "line": "rgba(34,31,28,0.10)",
        "pattern": "seeds",
    },
    {
        "key": "midnight", "name": "深夜电波",
        "bg1": "#141428", "bg2": "#05050C", "surface": "#171730", "surface2": "#1F1F3D",
        "ink": "#F4F2FF", "ink2": "#B6B1D6", "ink3": "#7B76A2",
        "accent": "#9B8CFF", "accent2": "#4DE1FF", "line": "rgba(244,242,255,0.12)",
        "pattern": "stars",
    },
    {
        "key": "paper", "name": "手账米白",
        "bg1": "#F5EEDA", "bg2": "#E5D6BC", "surface": "#FCF8EF", "surface2": "#F3EAD8",
        "ink": "#33291F", "ink2": "#6B5B48", "ink3": "#A2907A",
        "accent": "#C0392B", "accent2": "#C89F5D", "line": "rgba(51,41,31,0.12)",
        "pattern": "rule",
    },
    {
        "key": "cyber", "name": "赛博荧光",
        "bg1": "#0C0418", "bg2": "#1A0033", "surface": "#150B26", "surface2": "#210F3A",
        "ink": "#EAFBFF", "ink2": "#A9B8D8", "ink3": "#6E7C9E",
        "accent": "#00F5D4", "accent2": "#FF2E97", "line": "rgba(234,251,255,0.12)",
        "pattern": "grid",
    },
    {
        "key": "gold", "name": "金箔典藏",
        "bg1": "#1D1913", "bg2": "#080706", "surface": "#17140F", "surface2": "#221D15",
        "ink": "#F7EFDD", "ink2": "#C9BCA0", "ink3": "#8A806B",
        "accent": "#E8C46A", "accent2": "#FFF1C9", "line": "rgba(247,239,221,0.12)",
        "pattern": "foil",
    },
]


def _money(value: Any) -> str:
    return "¥%s" % format(float(value or 0), ",.2f")


def _int(value: Any) -> str:
    return format(int(round(float(value or 0))), ",")


def _pct(value: Any, digits: int = 1) -> str:
    return ("%." + str(digits) + "f%%") % float(value or 0)


def _store_short(name: str) -> str:
    text = str(name or "")
    for token in ("麦当劳（", "麦当劳(", "）", ")"):
        text = text.replace(token, "")
    return text or "—"


# ------------------------------------------------------------------ 卡面构建


def _card_id(report: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "id", "name": "角色卡", "en": "PERSONA ID",
        "subtitle": "%s · %s" % (p["title"], p["element"] + "属性"),
        "blocks": [
            {"kind": "quote", "text": p["quote"], "slogan": p["slogan"]},
            {"kind": "attrs", "title": "五维", "items": p["attributes"]},
        ],
    }


def _card_stats(report: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    o, nu, it = report["overview"], report["nutrition"], report["items"]
    top = (it.get("top") or [])[:3]
    return {
        "type": "stats", "name": "战绩卡", "en": "BATTLE RECORD",
        "subtitle": "%d 单 · 跨越 %d 天" % (o["orderCount"], o["spanDays"]),
        "blocks": [
            {"kind": "metrics", "items": [
                {"k": "累计消费", "v": _money(o["totalSpend"]), "size": "xl",
                 "note": "%s ~ %s" % (o.get("firstOrder") or "—", o.get("lastOrder") or "—")},
                {"k": "订单数", "v": _int(o["orderCount"]), "unit": "单"},
                {"k": "客单价", "v": _money(o["avgTicket"])},
            ]},
            {"kind": "list", "title": "本命单品 TOP3", "items": [
                {"rank": i + 1, "name": x["name"], "value": "×%d" % x["qty"],
                 "note": "%s kcal · %d 单" % (_int(x["kcal"]), x["orders"])}
                for i, x in enumerate(top)
            ] if top else [], "empty": "还没有足够的下单记录"},
            {"kind": "facts", "title": "热量账单", "items": [
                ["累计热量", "%s kcal" % _int(nu["energyKcal"])],
                ["≈ 巨无霸", "%.1f 个" % nu["bigMacEquivalent"]],
                ["≈ 慢跑", "%.0f 公里" % nu["runKmEquivalent"]],
                ["累计钠", "%s mg" % _int(nu["sodium"])],
            ]},
        ],
    }


def _card_rhythm(report: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    o, t, f = report["overview"], report["trends"], p["facts"]
    night = int(f["night"])
    peak_label = ("%02d:00" % f["peak"]) if f["peak"] >= 0 else "—"
    if f["night_pct"] >= 20:
        insight = "深夜订单占到 %s，夜里比白天更常出现。" % _pct(f["night_pct"], 0)
    elif night:
        insight = "22 点后只下了 %d 单，作息还在正轨上。" % night
    else:
        insight = "没有深夜订单，这份节律表干净得让人羡慕。"
    return {
        "type": "rhythm", "name": "节律卡", "en": "DAILY RHYTHM",
        "subtitle": "最活跃 %s · 深夜 %s" % (peak_label, _pct(f["night_pct"], 0)),
        "blocks": [
            {"kind": "hour24", "title": "24 小时下单节律",
             "series": [b["orders"] for b in t.get("byHour") or []],
             "nightFrom": 22, "nightTo": 5},
            {"kind": "metrics", "items": [
                {"k": "深夜食堂指数", "v": _pct(f["night_pct"], 0), "tone": "warn" if f["night_pct"] >= 20 else "good",
                 "note": "%d 单落在 22:00–05:00" % night},
                {"k": "活跃时段", "v": peak_label, "note": "下单最集中的小时"},
                {"k": "据点", "v": _store_short(o.get("topStore")), "size": "sm",
                 "note": "%d 单 · %s" % (o["topStoreCount"], _pct(f["store_pct"], 0))},
            ]},
            {"kind": "week", "title": "一周分布",
             "labels": ["一", "二", "三", "四", "五", "六", "日"],
             "series": [b["orders"] for b in t.get("byWeekday") or []]},
            {"kind": "note", "text": insight,
             "tone": "warn" if f["night_pct"] >= 20 else "info"},
        ],
    }


def _card_wallet(report: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    pt, wa, f = report["points"], report["wallet"], p["facts"]
    names = [n for n in (wa.get("claimableNames") or []) if n][:3]
    if pt["expiringThisMonth"] > 0:
        insight = "本月有 %.0f 分即将过期，先兑券比继续攒着划算。" % pt["expiringThisMonth"]
        tone = "warn"
    elif pt["sleeping"] > 0:
        insight = "已经损失 %.0f 分，剩下的 %.1f 分记得在有效期内用掉。" % (pt["expired"], pt["available"])
        tone = "warn"
    else:
        insight = "积分没有损耗，账面上的每一分都还活着。"
        tone = "info"
    return {
        "type": "wallet", "name": "钱包卡", "en": "WALLET LEDGER",
        "subtitle": "可用 %.1f 分 · %d 张券待领" % (pt["available"], wa["claimableCoupons"]),
        "blocks": [
            {"kind": "metrics", "items": [
                {"k": "可用积分", "v": "%.1f" % pt["available"], "size": "xl",
                 "note": "累计 %.1f 分" % pt["accumulative"]},
                {"k": "沉睡积分", "v": "%.1f" % pt["sleeping"], "tone": "warn" if pt["sleeping"] > 0 else "good",
                 "note": "已过期 %.0f + 本月将过期 %.0f" % (pt["expired"], pt["expiringThisMonth"])},
            ]},
            {"kind": "gauge", "value": round(f["sleeping_pct"], 1),
             "label": "积分损耗率", "tone": "warn" if f["sleeping_pct"] >= 10 else "good",
             "note": "每 100 积分里有 %.0f 分正在过期" % f["sleeping_pct"]},
            {"kind": "facts", "title": "钱包与商城", "items": [
                ["持有优惠券", "%d 张" % wa["ownedCoupons"]],
                ["当前可领", "%d 张" % wa["claimableCoupons"]],
                ["积分抽奖", "每次 %d 分 · %d 项奖池" % (wa["lotteryPoint"], wa["lotteryPrizes"])],
                ["已中奖品", "%d 项" % wa["prizes"]],
                ["商城订单", "%d 笔" % wa["mallOrders"]],
            ]},
            {"kind": "tags", "title": "待领取", "items": names, "empty": "暂无待领取的券"},
            {"kind": "note", "text": insight, "tone": tone},
        ],
    }


def _card_badge(report: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    nxt = next((b for b in p["badges"] if not b["unlocked"]), None)
    goal = ("下一枚：%s · %s" % (nxt["name"], nxt["need"])) if nxt else "十枚徽章全部点亮，成就墙已满。"
    return {
        "type": "badge", "name": "徽章卡", "en": "TROPHY WALL",
        "subtitle": "已解锁 %d / %d 枚" % (p["badgeSummary"]["unlocked"], p["badgeSummary"]["total"]),
        "blocks": [
            {"kind": "badges", "items": p["badges"]},
            {"kind": "progress", "title": "徽章收集进度",
             "value": p["badgeSummary"]["unlocked"], "total": p["badgeSummary"]["total"],
             "note": "徽章由订单、积分、券、营养四类数据判定，重跑脚本会随数据变化"},
            {"kind": "note", "text": goal, "tone": "info"},
            {"kind": "facts", "title": "战力构成", "items": [
                ["五维加权", "%.1f" % p["powerBase"]],
                ["加成项", "+%d" % sum(b["value"] for b in p["powerBonus"])],
                ["最终战力", "%.1f" % p["power"]],
                ["稀有度", p["rarity"]["name"]],
            ]},
        ],
    }


CARD_BUILDERS = (_card_id, _card_stats, _card_rhythm, _card_wallet, _card_badge)


def build_card(report: Dict[str, Any], persona: Dict[str, Any] = None) -> Dict[str, Any]:
    """组装完整的卡片数据包（5 张卡面 + 5 套主题 + 稀有度阶梯）。"""
    from persona import RARITY_LADDER

    p = persona or report.get("persona") or derive_persona(report)
    cards = []
    for builder in CARD_BUILDERS:
        cards.append(builder(report, p))

    return {
        "meta": {
            "generatedAt": report.get("meta", {}).get("generatedAt") or "",
            "mode": report.get("meta", {}).get("mode") or "live",
            "version": "1.0",
            "source": "麦当劳 MCP · 只读数据",
        },
        "persona": p,
        "themes": THEMES,
        "ladder": RARITY_LADDER,
        "cards": cards,
        "defaultCard": "id",
        "defaultTheme": p.get("style") or "classic",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成麦麦角色卡数据")
    parser.add_argument("--data", help="report.json 路径")
    parser.add_argument("--sample", action="store_true", help="使用内置演示数据")
    parser.add_argument("--out", default="card.json", help="输出路径，默认 card.json")
    parser.add_argument("--pretty", action="store_true", help="缩进输出")
    args = parser.parse_args(argv)

    if args.sample:
        with open(SAMPLE_RAW, encoding="utf-8") as fh:
            report = build_report(json.load(fh), mode="sample")
        print("已载入内置演示数据（assets/sample-raw.json）")
    elif args.data:
        with open(args.data, encoding="utf-8") as fh:
            report = json.load(fh)
        print("已载入 %s" % args.data)
    else:
        parser.error("需要 --data report.json 或 --sample")
        return 2

    payload = build_card(report)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2 if args.pretty else None)

    p = payload["persona"]
    print()
    print("========== 麦麦角色卡 ==========")
    print("角色          %s · %s" % (p["name"], p["title"]))
    print("稀有度        %s（战力 %.1f）" % (p["rarity"]["name"], p["power"]))
    print("默认主题      %s" % payload["defaultTheme"])
    print("卡面数量      %d" % len(payload["cards"]))
    print("徽章          %d / %d" % (p["badgeSummary"]["unlocked"], p["badgeSummary"]["total"]))
    print("已写入        %s" % os.path.abspath(args.out))
    print("================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
