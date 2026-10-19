"""用户画像 → 麦麦角色卡档案。

把 `report.json` 里已经算好的指标，映射成一张「角色卡」需要的全部叙事元素：
稀有度、称号、五维属性、外观参数、台词、成就徽章。

设计原则
--------
1. **确定性**：同一个账号永远得到同一个角色。所有随机项都由账号指纹播种，
   换账号才换人设；重跑脚本不会「重roll」。
2. **可解释**：稀有度不是玄学，五维和加成项都能在卡片上逐条列出。
3. **纯标准库**：不引入任何第三方依赖，也不发网络请求。
"""

from __future__ import annotations

import random
import zlib
from typing import Any, Dict, List

# ------------------------------------------------------------------ 稀有度阶梯
# 由低到高：蓝 → 绿 → 紫 → 金 → 红。数值为「战力」门槛。
RARITY_LADDER: List[Dict[str, Any]] = [
    {"key": "blue", "name": "蓝色品质", "tier": "普通", "stars": 1,
     "color": "#3B82F6", "deep": "#1D4ED8", "glow": "#93C5FD", "min": 0},
    {"key": "green", "name": "绿色品质", "tier": "精良", "stars": 2,
     "color": "#22C55E", "deep": "#15803D", "glow": "#86EFAC", "min": 40},
    {"key": "purple", "name": "紫色品质", "tier": "稀有", "stars": 3,
     "color": "#A855F7", "deep": "#7E22CE", "glow": "#E9D5FF", "min": 56},
    {"key": "gold", "name": "金色品质", "tier": "史诗", "stars": 4,
     "color": "#F5B301", "deep": "#B45309", "glow": "#FFE08A", "min": 72},
    {"key": "red", "name": "红色品质", "tier": "传说", "stars": 5,
     "color": "#EF4444", "deep": "#B91C1C", "glow": "#FFB3A7", "min": 87},
]

# ------------------------------------------------------------------ 角色原型
# 每个原型 = 一套叙事（称号/台词/配色/外观倾向/默认卡面主题）。
ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "night_keeper": {
        "title": "深夜守夜人", "code": "NIGHT KEEPER", "element": "夜",
        "desc": "城市熄灯之后，你的加餐时间才刚开始。",
        "slogan": ["夜晚不打烊", "零点补给官", "灯灭了，堡还热"],
        "nick": ["小夜", "宵夜侠", "零点麦", "夜航仔"],
        "quote": "22 点之后的单占了 {night_pct}，城市的灯灭了，我的堡还热着。",
        "accent": "#6D5BD0", "theme": "midnight",
        "look": {"hair": ["messy", "short", "bob"], "prop": ["cup", "burger"],
                 "accessory": ["headset", "none"], "expression": "sleepy"},
    },
    "loyalist": {
        "title": "本命信徒", "code": "LOYALIST", "element": "火",
        "desc": "菜单翻了无数遍，最后还是点那一个。",
        "slogan": ["本命不改", "只点那一份", "老样子，谢谢"],
        "nick": ["小薯", "阿堡", "堡堡", "老样子"],
        "quote": "点过 {distinct} 种，{loyalty_pct} 的都点了第二次。菜单很大，我只认那几样。",
        "accent": "#E03A2F", "theme": "classic",
        "look": {"hair": ["bob", "ponytail", "short"], "prop": ["burger", "fries"],
                 "accessory": ["cap", "ribbon", "none"], "expression": "smile"},
    },
    "sleepy_rich": {
        "title": "沉睡财主", "code": "SLEEPING TYCOON", "element": "金",
        "desc": "账面积分一大把，全在睡觉。",
        "slogan": ["积分在睡觉", "别让它过期", "账面富翁"],
        "nick": ["积分仔", "金库麦", "阿积"],
        "quote": "{sleeping} 积分已经过期或即将过期——我攒得住，但攒不过保质期。",
        "accent": "#C79A2E", "theme": "gold",
        "look": {"hair": ["bun", "short", "bob"], "prop": ["sundae", "pie"],
                 "accessory": ["glasses", "none"], "expression": "gentle"},
    },
    "explorer": {
        "title": "探店猎人", "code": "EXPLORER", "element": "风",
        "desc": "菜单没有死角，新品味一个不落。",
        "slogan": ["菜单无死角", "新品猎人", "都尝一遍"],
        "nick": ["小探", "阿新", "菜单猎人"],
        "quote": "一路点过 {distinct} 种商品，菜单对我来说是一张待解锁的地图。",
        "accent": "#2F7D6E", "theme": "paper",
        "look": {"hair": ["ponytail", "twin", "messy"], "prop": ["nuggets", "sundae"],
                 "accessory": ["cap", "glasses"], "expression": "energetic"},
    },
    "value_hunter": {
        "title": "精算猎人", "code": "VALUE HUNTER", "element": "水",
        "desc": "券不落地，单不失手，一块钱掰成两半花。",
        "slogan": ["券不落地", "一单不亏", "精算到分"],
        "nick": ["券王", "小算", "阿省"],
        "quote": "客单价稳在 {avg}，还盯着 {claimable} 张没领的券——省钱这件事我是认真的。",
        "accent": "#1F7A8C", "theme": "classic",
        "look": {"hair": ["short", "bob"], "prop": ["fries", "cup"],
                 "accessory": ["glasses"], "expression": "cool"},
    },
    "kcal_warrior": {
        "title": "热量战士", "code": "KCAL WARRIOR", "element": "炎",
        "desc": "每一卡都吃进了战绩里。",
        "slogan": ["热量即战绩", "卡路里收藏家", "吃出战斗力"],
        "nick": ["阿热", "卡路里麦", "大口仔"],
        "quote": "平均每单 {kcal_order} kcal，累计 {bigmac} 个巨无霸——我的热血是有热量的。",
        "accent": "#D9480F", "theme": "cyber",
        "look": {"hair": ["short", "messy", "twin"], "prop": ["burger", "nuggets"],
                 "accessory": ["none", "headset"], "expression": "energetic"},
    },
    "steady": {
        "title": "日常打卡人", "code": "DAILY REGULAR", "element": "土",
        "desc": "不追新，不熬夜，到点就吃。",
        "slogan": ["到点就吃", "稳定输出", "日常在场"],
        "nick": ["老麦", "阿常", "打卡仔"],
        "quote": "{orders} 单，{span} 天，日子被一顿顿稳稳地接住了。",
        "accent": "#8A6A3B", "theme": "paper",
        "look": {"hair": ["short", "bun", "bob"], "prop": ["cup", "burger"],
                 "accessory": ["none", "ribbon"], "expression": "smile"},
    },
    "rookie": {
        "title": "麦麦新客", "code": "ROOKIE", "element": "光",
        "desc": "故事刚刚翻开第一页。",
        "slogan": ["故事刚开始", "第一次见面", "先点个本命"],
        "nick": ["小新", "初见麦", "阿初"],
        "quote": "目前只有 {orders} 单记录——角色的成长线，才刚写到开头。",
        "accent": "#C8102E", "theme": "classic",
        "look": {"hair": ["bob", "short", "twin"], "prop": ["fries", "cup"],
                 "accessory": ["ribbon", "none"], "expression": "smile"},
    },
}

HAIR_COLORS = ["#2B2620", "#3D2B1F", "#5A3A26", "#7A3E2A", "#8B5A2B", "#C9974A", "#E8D6BC"]
SKIN_TONES = ["#F8D9C4", "#F2C6A8", "#E3B08C", "#CE9367"]

# ------------------------------------------------------------------ 成就徽章
# 每枚徽章 = (key, 图标, 名称, 判定函数, 获取条件文案)
BADGES: List[Dict[str, Any]] = [
    {"key": "first", "icon": "🍔", "name": "初次见面", "need": "完成第 1 单",
     "test": lambda f: f["orders"] >= 1},
    {"key": "hundred", "icon": "🏅", "name": "百单老友", "need": "累计 100 单",
     "test": lambda f: f["orders"] >= 100},
    {"key": "spender", "icon": "💰", "name": "千元食客", "need": "累计消费 ¥1000",
     "test": lambda f: f["spend"] >= 1000},
    {"key": "night", "icon": "🌙", "name": "深夜会员", "need": "深夜订单占比 ≥ 20%",
     "test": lambda f: f["night_pct"] >= 20},
    {"key": "monogamy", "icon": "🎯", "name": "本命专一", "need": "单品占比 ≥ 30%",
     "test": lambda f: f["top_share"] >= 30},
    {"key": "points", "icon": "🏦", "name": "积分囤积", "need": "可用积分 ≥ 500",
     "test": lambda f: f["points"] >= 500},
    {"key": "coupon", "icon": "🎟️", "name": "券场老手", "need": "可领券 ≥ 3 张",
     "test": lambda f: f["claimable"] >= 3},
    {"key": "kcal", "icon": "🔥", "name": "热量巨人", "need": "累计热量 ≥ 20 个巨无霸",
     "test": lambda f: f["bigmac"] >= 20},
    {"key": "explorer", "icon": "🧭", "name": "菜单猎人", "need": "点过 20 种商品",
     "test": lambda f: f["distinct"] >= 20},
    {"key": "legend", "icon": "👑", "name": "传说食神", "need": "战力 ≥ 87（红色品质）",
     "test": lambda f: f["power"] >= 87},
]


# ------------------------------------------------------------------ 小工具


def _sat(value: float, mid: float) -> float:
    """饱和函数：value == mid 时得 50 分，永不越界到 100 以上。"""
    value = max(0.0, float(value or 0))
    if mid <= 0:
        return 0.0
    return round(100.0 * value / (value + mid), 1)


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100.0, 1) if whole else 0.0


def _tone(score: float) -> str:
    """五维分档，用于卡面上的评语。"""
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    if score >= 35:
        return "C"
    return "D"


def _fingerprint(report: Dict[str, Any]) -> Dict[str, Any]:
    """账号指纹：只取订单号/门店/首单日期，稳定且不含个人信息。"""
    overview = report.get("overview") or {}
    items = report.get("items") or {}
    seed_src = "|".join([
        str(overview.get("firstOrder") or ""),
        str(overview.get("lastOrder") or ""),
        str(overview.get("orderCount") or 0),
        str(round(float(overview.get("totalSpend") or 0), 2)),
        str(items.get("totalCount") or 0),
        str(overview.get("topStore") or ""),
    ])
    crc = zlib.crc32(seed_src.encode("utf-8")) & 0xFFFFFFFF
    return {
        "crc": crc,
        "seed": crc,
        "short": "%04X" % (crc & 0xFFFF),
    }


def _facts(report: Dict[str, Any]) -> Dict[str, Any]:
    """把报告里的数值压平成一套「可读事实」，供台词与徽章使用。"""
    overview = report.get("overview") or {}
    trends = report.get("trends") or {}
    items = report.get("items") or {}
    nutrition = report.get("nutrition") or {}
    points = report.get("points") or {}
    wallet = report.get("wallet") or {}

    orders = int(overview.get("orderCount") or 0)
    by_hour = trends.get("byHour") or []
    night = sum(int(b.get("orders") or 0) for b in by_hour
                if int(b.get("hour") or 0) >= 22 or int(b.get("hour") or 0) < 5)
    top = (items.get("top") or [{}])[0] if items.get("top") else {}
    total_units = int(items.get("totalCount") or 0)
    accum = float(points.get("accumulative") or 0)

    return {
        "orders": orders,
        "spend": float(overview.get("totalSpend") or 0),
        "avg": float(overview.get("avgTicket") or 0),
        "span": int(overview.get("spanDays") or 0),
        "units": total_units,
        "distinct": int(items.get("distinctCount") or 0),
        "loyalty": float(items.get("loyaltyRate") or 0),
        "night": night,
        "night_pct": _pct(night, orders),
        "kcal": float(nutrition.get("energyKcal") or 0),
        "kcal_order": float(nutrition.get("perOrderKcal") or 0),
        "bigmac": float(nutrition.get("bigMacEquivalent") or 0),
        "sodium": float(nutrition.get("sodium") or 0),
        "points": float(points.get("available") or 0),
        "accum": accum,
        "sleeping": float(points.get("sleeping") or 0),
        "sleeping_pct": _pct(float(points.get("sleeping") or 0), accum),
        "claimable": int(wallet.get("claimableCoupons") or 0),
        "owned": int(wallet.get("ownedCoupons") or 0),
        "top": str(top.get("name") or ""),
        "top_qty": int(top.get("qty") or 0),
        "top_share": _pct(int(top.get("qty") or 0), total_units),
        "store": str(overview.get("topStore") or ""),
        "store_pct": _pct(int(overview.get("topStoreCount") or 0), orders),
        "peak": int(overview.get("busiestHour") if overview.get("busiestHour") is not None else -1),
    }


# ------------------------------------------------------------------ 五维与稀有度


def _attributes(f: Dict[str, Any]) -> List[Dict[str, Any]]:
    """五维属性。每项都能从报告里找到出处，卡面上会标注依据。"""
    loyal = round(
        min(100.0, _sat(f["orders"], 20) * 0.45 + min(100.0, f["loyalty"]) * 0.55), 1
    )
    return [
        {"key": "食力", "value": _sat(f["units"], 45),
         "note": "%d 件商品" % f["units"]},
        {"key": "财力", "value": _sat(f["spend"], 900),
         "note": "¥%s" % format(f["spend"], ",.0f")},
        {"key": "忠诚", "value": loyal,
         "note": "复购率 %.0f%%" % f["loyalty"]},
        {"key": "夜行", "value": min(100.0, round(f["night_pct"] / 22.0 * 100, 1)),
         "note": "深夜 %.0f%%" % f["night_pct"]},
        {"key": "探索", "value": _sat(f["distinct"], 16),
         "note": "%d 种商品" % f["distinct"]},
    ]


def _bonus(f: Dict[str, Any]) -> List[Dict[str, Any]]:
    """稀有度加成项：解释「为什么是这个品质」，每项都带可读理由。"""
    out: List[Dict[str, Any]] = []
    if f["span"] >= 180:
        out.append({"label": "长期陪伴", "value": 4, "note": "跨越 %d 天" % f["span"]})
    elif f["span"] >= 90:
        out.append({"label": "稳定在场", "value": 2, "note": "跨越 %d 天" % f["span"]})
    if f["top_share"] >= 25:
        out.append({"label": "本命专一", "value": 3,
                    "note": "%s 占 %.0f%%" % (f["top"], f["top_share"])})
    if f["claimable"] >= 3:
        out.append({"label": "券场活跃", "value": 2, "note": "%d 张可领" % f["claimable"]})
    if f["bigmac"] >= 30:
        out.append({"label": "热量大户", "value": 3, "note": "%.0f 个巨无霸" % f["bigmac"]})
    if f["night_pct"] >= 25:
        out.append({"label": "夜行体质", "value": 2, "note": "深夜 %.0f%%" % f["night_pct"]})
    return out


def _power(attrs: List[Dict[str, Any]], bonus: List[Dict[str, Any]]) -> Dict[str, Any]:
    """战力 = 五维加权 + 加成项，封顶 100。"""
    weight = {"食力": 0.26, "财力": 0.30, "忠诚": 0.22, "夜行": 0.10, "探索": 0.12}
    base = sum(a["value"] * weight.get(a["key"], 0.0) for a in attrs)
    extra = sum(b["value"] for b in bonus)
    total = min(100.0, round(base + extra, 1))
    return {"base": round(base, 1), "bonus": extra, "total": total}


def _rarity(power: float) -> Dict[str, Any]:
    chosen = RARITY_LADDER[0]
    for tier in RARITY_LADDER:
        if power >= tier["min"]:
            chosen = tier
    return dict(chosen)


def _pick_archetype(f: Dict[str, Any]) -> Dict[str, str]:
    """原型判定：按优先级命中第一条，命中即停，便于在卡面上解释「为什么是你」。

    顺序即稀有度：越靠前的特质越少见，避免所有人都被归到「日常打卡人」。
    """
    if f["orders"] < 4:
        return {"key": "rookie", "reason": "订单不足 4 单，故事刚开始"}
    if f["night_pct"] >= 25:
        return {"key": "night_keeper", "reason": "深夜订单占比 %.0f%% ≥ 25%%" % f["night_pct"]}
    if f["sleeping"] >= 200 and f["sleeping_pct"] >= 15:
        return {"key": "sleepy_rich", "reason": "%.0f 分积分正在过期" % f["sleeping"]}
    if f["top_share"] >= 25:
        return {"key": "loyalist", "reason": "%s 占全部件数 %.0f%%" % (f["top"], f["top_share"])}
    if f["loyalty"] >= 70:
        return {"key": "loyalist", "reason": "复购率 %.0f%% ≥ 70%%" % f["loyalty"]}
    if f["kcal_order"] >= 800:
        return {"key": "kcal_warrior", "reason": "平均每单 %.0f kcal" % f["kcal_order"]}
    if f["distinct"] >= 18:
        return {"key": "explorer", "reason": "点过 %d 种商品" % f["distinct"]}
    if f["avg"] <= 28 and f["claimable"] >= 2:
        return {"key": "value_hunter", "reason": "客单价 ¥%.2f 且可领 %d 张券" % (f["avg"], f["claimable"])}
    return {"key": "steady", "reason": "%d 单稳定分布，无极端偏好" % f["orders"]}


def _mix_hex(a: str, b: str, t: float) -> str:
    """两个 #RRGGBB 之间线性插值。"""
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    x, y = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(int(round(x[i] + (y[i] - x[i]) * t)) for i in range(3))


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _look(arch: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """外观参数：由原型给候选集，账号指纹决定具体取值。

    额外做一次「发色 vs 肤色」对比度校正——两者太接近时角色会像没头发。
    """
    spec = arch["look"]
    skin = rng.choice(SKIN_TONES)
    hair = rng.choice(HAIR_COLORS)
    guard = 0
    while abs(_lum(hair) - _lum(skin)) < 0.24 and guard < 6:
        hair = _mix_hex(hair, "#2E211A", 0.42)
        guard += 1

    return {
        "hair": rng.choice(spec["hair"]),
        "hairColor": hair,
        "skin": skin,
        "prop": rng.choice(spec["prop"]),
        "accessory": rng.choice(spec["accessory"]),
        "expression": spec["expression"],
        "outfit": arch["accent"],
        "trim": "#FFFFFF",
    }


def _quote(arch: Dict[str, Any], f: Dict[str, Any]) -> str:
    try:
        return arch["quote"].format(
            orders=f["orders"], spend=format(f["spend"], ",.0f"),
            avg="¥%.2f" % f["avg"], span=f["span"], units=f["units"],
            distinct=f["distinct"], loyalty_pct="%.0f%%" % f["loyalty"],
            night=f["night"], night_pct="%.0f%%" % f["night_pct"],
            kcal=format(f["kcal"], ",.0f"), kcal_order="%.0f" % f["kcal_order"],
            bigmac="%.1f" % f["bigmac"], top=f["top"] or "本命",
            points="%.0f" % f["points"], sleeping="%.0f" % f["sleeping"],
            claimable=f["claimable"], store=f["store"] or "常去门店",
        )
    except (KeyError, IndexError):  # 模板写错时不要让整条链路崩掉
        return arch["desc"]


# ------------------------------------------------------------------ 对外入口


def derive_persona(report: Dict[str, Any]) -> Dict[str, Any]:
    """报告 → 角色档案。保证幂等：同一份报告永远得到同一张卡。"""
    f = _facts(report)
    fp = _fingerprint(report)
    rng = random.Random(fp["seed"])

    key = _pick_archetype(f)
    arch = ARCHETYPES[key["key"]]
    attrs = _attributes(f)
    bonus = _bonus(f)
    power = _power(attrs, bonus)
    rarity = _rarity(power["total"])
    f["power"] = power["total"]

    badges = []
    for spec in BADGES:
        ok = bool(spec["test"](f))
        badges.append({"key": spec["key"], "icon": spec["icon"], "name": spec["name"],
                       "need": spec["need"], "unlocked": ok})
    unlocked = sum(1 for b in badges if b["unlocked"])

    profile = [
        {"k": "身份", "v": arch["title"]},
        {"k": "属性", "v": arch["element"] + " · " + rarity["tier"]},
        {"k": "本命", "v": f["top"] or "尚未确定"},
        {"k": "据点", "v": (f["store"] or "尚未记录").replace("麦当劳（", "").replace("）", "")},
        {"k": "活跃时段", "v": ("%02d:00 前后" % f["peak"]) if f["peak"] >= 0 else "—"},
        {"k": "统计跨度", "v": "%d 天" % f["span"]},
    ]

    return {
        "version": "1.0",
        "seed": fp["seed"],
        "fingerprint": fp["short"],
        "cardNo": "MCD-%s-%s" % (("%04d" % f["orders"])[-4:], fp["short"]),
        "archetype": key["key"],
        "archetypeReason": key["reason"],
        "name": rng.choice(arch["nick"]),
        "title": arch["title"],
        "codename": arch["code"],
        "element": arch["element"],
        "desc": arch["desc"],
        "slogan": rng.choice(arch["slogan"]),
        "quote": _quote(arch, f),
        "rarity": rarity,
        "power": power["total"],
        "powerBase": power["base"],
        "powerBonus": bonus,
        "attributes": [
            {"key": a["key"], "value": a["value"], "note": a["note"], "tone": _tone(a["value"])}
            for a in attrs
        ],
        "profile": profile,
        "badges": badges,
        "badgeSummary": {"unlocked": unlocked, "total": len(badges)},
        "look": _look(arch, rng),
        "style": arch["theme"],
        "facts": {k: v for k, v in f.items() if k != "power"},
    }
