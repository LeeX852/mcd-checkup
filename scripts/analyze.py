"""体检指标计算：把麦当劳 MCP 返回的原始数据算成一份「体检报告」的数据模型。

输入是各工具的原始 dict，输出是给前端渲染用的 report dict。
纯标准库实现，不依赖任何第三方包。
"""

from __future__ import annotations

import datetime as dt
import difflib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from persona import derive_persona

# ------------------------------------------------------------------ 常量参考值

DAILY_SODIUM_MG = 2000.0       # 《中国居民膳食指南》成人每日钠推荐上限
MEAL_KCAL_REF = 650.0          # 一餐参考热量
BIG_MAC_KCAL = 513.0           # 巨无霸
RICE_BOWL_KCAL = 232.0         # 一碗米饭（约 200g）
RUN_KCAL_PER_KM = 62.0         # 60kg 成年人慢跑每公里消耗

PAREN_RE = re.compile(r"[（(\[【][^）)\]】]*[）)\]】]")
NOISE_RE = re.compile(r"[\s·•、,，/]+")


def _bigrams(text: str) -> set:
    """中文二元字组，用于兜底相似度。"""
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


# ------------------------------------------------------------------ 通用小工具


def _num(value: Any, default: float = 0.0) -> float:
    """MCP 大量字段是字符串数字，统一兜底转换。"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else default


def _clean_name(name: str) -> str:
    """清洗商品名：去掉规格/温度/备注等括号噪声，便于和营养表对齐。"""
    if not name:
        return ""
    text = PAREN_RE.sub("", str(name))
    text = NOISE_RE.sub("", text)
    return text.strip()


def _as_list(data: Any, *key_candidates: str) -> List[Any]:
    """MCP 各家工具的返回套壳不一致，这里做一次统一降维。"""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in key_candidates:
            value = data.get(key)
            if isinstance(value, list):
                return value
        for value in data.values():
            if isinstance(value, list):
                return value
    return []


# ------------------------------------------------------------------ 营养表解析


def parse_nutrition_table(raw: Any) -> Dict[str, Dict[str, float]]:
    """解析 list-nutrition-foods 返回的紧凑表格文本。

    形如::

        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,...}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    if isinstance(raw, list):
        rows = raw
        out: Dict[str, Dict[str, float]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("productName") or "").strip()
            if name:
                out[name] = _row_to_metrics(row)
        return out

    if not isinstance(raw, str):
        return {}

    out = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("{"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 9:
            continue
        name, _, kj, kcal, protein, fat, carb, sodium, calcium = parts[:9]
        if not name or name.lower() == "null":
            continue
        record = {
            "energyKj": _num(kj),
            "energyKcal": _num(kcal),
            "protein": _num(protein),
            "fat": _num(fat),
            "carbohydrate": _num(carb),
            "sodium": _num(sodium),
            "calcium": _num(calcium),
        }
        # 同名后来者覆盖前者，保证 table 里重复条目只留一条
        out[name] = record
    return out


def _row_to_metrics(row: Dict[str, Any]) -> Dict[str, float]:
    return {
        "energyKj": _num(row.get("energyKj")),
        "energyKcal": _num(row.get("energyKcal")),
        "protein": _num(row.get("protein")),
        "fat": _num(row.get("fat")),
        "carbohydrate": _num(row.get("carbohydrate")),
        "sodium": _num(row.get("sodium")),
        "calcium": _num(row.get("calcium")),
    }


class NutritionIndex:
    """营养表 + 模糊匹配。"""

    FIELDS = ("energyKcal", "energyKj", "protein", "fat", "carbohydrate", "sodium", "calcium")

    def __init__(self, table: Dict[str, Dict[str, float]]):
        self.table = table
        self.cleaned = {_clean_name(k): k for k in table if _clean_name(k)}
        self.names = list(self.cleaned.keys())
        self._cache: Dict[str, Optional[str]] = {}

    def match(self, product_name: str) -> Optional[Dict[str, float]]:
        key = self._match_key(product_name)
        if key is None:
            return None
        return dict(self.table[self.cleaned[key]])

    def _match_key(self, product_name: str) -> Optional[str]:
        raw = str(product_name or "").strip()
        if not raw or not self.cleaned:
            return None
        if raw in self._cache:
            return self._cache[raw]

        target = _clean_name(raw)
        result: Optional[str] = None

        # 1) 原名精确 / 清洗后精确 / 去括号后精确
        if target in self.cleaned:
            result = target
        else:
            # 2) 包含匹配：营养表名称是商品名的子串，取最长命中
            candidates = [n for n in self.names if n and n in target]
            if not candidates:
                candidates = [n for n in self.names if target and target in n]
            if candidates:
                result = max(candidates, key=len)
            elif target:
                # 3) 模糊兜底：编辑距离 + 二元字组重合度（应对「麦旋风奥利奥」↔「奥利奥麦旋风」这类倒装名）
                best_name, best_score = None, 0.0
                for name in difflib.get_close_matches(target, self.names, n=3, cutoff=0.55):
                    score = difflib.SequenceMatcher(None, target, name).ratio()
                    if score > best_score:
                        best_name, best_score = name, score
                if best_score >= 0.62:
                    result = best_name
                else:
                    grams = _bigrams(target)
                    for name in self.names:
                        other = _bigrams(name)
                        if not other:
                            continue
                        overlap = len(grams & other) / len(grams | other)
                        if overlap > best_score:
                            best_name, best_score = name, overlap
                    if best_score >= 0.45:
                        result = best_name

        self._cache[raw] = result
        return result

    def match_name(self, product_name: str) -> Optional[str]:
        key = self._match_key(product_name)
        return self.cleaned.get(key) if key else None


# ------------------------------------------------------------------ 时间解析

TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y年%m月%d日 %H:%M:%S",
    "%Y%m%d%H%M%S",
)


def parse_time(value: Any) -> Optional[dt.datetime]:
    if isinstance(value, dt.datetime):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in TIME_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    if isinstance(value, (int, float)) and value > 10_000_000_000:
        stamp = value / 1000.0 if value > 10_000_000_000_000 else float(value)
        return dt.datetime.fromtimestamp(stamp)
    return None


# ------------------------------------------------------------------ 主分析函数


def build_report(raw: Dict[str, Dict[str, Any]], mode: str = "live") -> Dict[str, Any]:
    """把一轮 MCP 抓取结果汇总成报告数据。"""
    nutrition = NutritionIndex(parse_nutrition_table(raw.get("list-nutrition-foods", {}).get("data")))

    orders = _normalize_orders(raw.get("order-list", {}).get("data"))
    lines = _flatten_items(orders, nutrition)

    overview = _calc_overview(orders)
    trends = _calc_trends(orders)
    items = _calc_items(lines)
    nutrition_summary = _calc_nutrition(lines, nutrition)
    points = _calc_points(raw.get("query-my-account", {}).get("data"))
    wallet = _calc_wallet(raw)
    verdicts = _calc_verdicts(overview, trends, items, nutrition_summary, points, wallet)

    partial = {
        "meta": {"mode": mode},
        "overview": overview,
        "trends": trends,
        "items": items,
        "nutrition": nutrition_summary,
        "points": points,
        "wallet": wallet,
        "verdicts": verdicts,
    }
    # 角色画像：由同一份指标推导，保证报告与角色卡永远说的是同一套数据
    persona = derive_persona(partial)

    return {
        "meta": {
            "generatedAt": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "toolCalls": sorted(k for k, v in raw.items() if not v.get("error")),
            "errors": {k: v.get("error", "") for k, v in raw.items() if v.get("error")},
        },
        "overview": overview,
        "trends": trends,
        "items": items,
        "nutrition": nutrition_summary,
        "points": points,
        "wallet": wallet,
        "verdicts": verdicts,
        "persona": persona,
    }


def _normalize_orders(data: Any) -> List[Dict[str, Any]]:
    raw_list = _as_list(data, "list", "orders", "data")
    orders: List[Dict[str, Any]] = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        stamp = parse_time(row.get("createTime") or row.get("create_time") or row.get("orderTime"))
        orders.append(
            {
                "orderId": str(row.get("orderId") or row.get("orderNo") or ""),
                "time": stamp,
                "storeName": str(row.get("storeName") or row.get("store_name") or "未知门店"),
                "orderType": str(row.get("orderType") or ""),
                "status": str(row.get("orderStatus") or ""),
                "amount": _num(row.get("realTotalAmount") or row.get("payAmount") or row.get("totalAmount")),
                "products": _as_list(row.get("orderProductList"), "productList", "goods"),
            }
        )
    return orders


def _flatten_items(orders: List[Dict[str, Any]], nutrition: NutritionIndex) -> List[Dict[str, Any]]:
    """把订单拍平成「一行一个商品」的事实表，并挂上营养数据。"""
    lines: List[Dict[str, Any]] = []
    for order in orders:
        for product in order["products"]:
            if not isinstance(product, dict):
                continue
            name = str(product.get("productName") or product.get("name") or "").strip()
            qty = max(1, int(_num(product.get("quantity") or product.get("count"), 1)))
            children = _as_list(product.get("comboItemList"), "comboItems", "subItems")

            metrics: Optional[Dict[str, float]] = nutrition.match(name) if name else None
            matched = bool(metrics)
            if not matched and children:
                merged = _merge_children(children, nutrition)
                if merged:
                    metrics, matched = merged, True

            record = {
                "orderId": order["orderId"],
                "time": order["time"],
                "storeName": order["storeName"],
                "name": name or "未命名商品",
                "qty": qty,
                "matched": matched,
            }
            for field in NutritionIndex.FIELDS:
                record[field] = (metrics or {}).get(field, 0.0) * qty
            lines.append(record)
    return lines


def _merge_children(children: Iterable[Any], nutrition: NutritionIndex) -> Optional[Dict[str, float]]:
    total = {f: 0.0 for f in NutritionIndex.FIELDS}
    hit = False
    for child in children:
        if not isinstance(child, dict):
            continue
        name = str(child.get("productName") or child.get("name") or "").strip()
        if not name:
            continue
        metrics = nutrition.match(name)
        if not metrics:
            continue
        hit = True
        qty = max(1, int(_num(child.get("quantity") or child.get("count"), 1)))
        for field in NutritionIndex.FIELDS:
            total[field] += metrics.get(field, 0.0) * qty
    return total if hit else None


def _calc_overview(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not orders:
        return {
            "orderCount": 0, "totalSpend": 0.0, "avgTicket": 0.0, "itemCount": 0,
            "firstOrder": None, "lastOrder": None, "spanDays": 0,
            "topStore": None, "topStoreCount": 0, "busiestDayweek": None, "busiestHour": None,
        }
    stamps = [o["time"] for o in orders if o["time"]]
    total_spend = sum(o["amount"] for o in orders)
    store_counter = Counter(o["storeName"] for o in orders if o["storeName"])
    top_store, top_store_count = (store_counter.most_common(1)[0] if store_counter else (None, 0))

    span_days = 0
    if stamps:
        span_days = max(1, (max(stamps) - min(stamps)).days + 1)

    hour_counter = Counter(o["time"].hour for o in orders if o["time"])
    busiest_hour = hour_counter.most_common(1)[0][0] if hour_counter else None

    return {
        "orderCount": len(orders),
        "totalSpend": round(total_spend, 2),
        "avgTicket": round(total_spend / len(orders), 2),
        "firstOrder": min(stamps).strftime("%Y-%m-%d") if stamps else None,
        "lastOrder": max(stamps).strftime("%Y-%m-%d") if stamps else None,
        "spanDays": span_days,
        "topStore": top_store,
        "topStoreCount": top_store_count,
        "busiestHour": busiest_hour,
    }


WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _calc_trends(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    timed = [o for o in orders if o["time"]]
    month_counter: Dict[str, int] = defaultdict(int)
    month_spend: Dict[str, float] = defaultdict(float)
    for order in timed:
        key = order["time"].strftime("%Y-%m")
        month_counter[key] += 1
        month_spend[key] += order["amount"]

    hour_hist = [0] * 24
    weekday_hist = [0] * 7
    for order in timed:
        hour_hist[order["time"].hour] += 1
        weekday_hist[order["time"].weekday()] += 1

    months = sorted(month_counter)
    return {
        "byMonth": [
            {"label": m, "orders": month_counter[m], "spend": round(month_spend[m], 2)}
            for m in months
        ],
        "byHour": [{"hour": h, "orders": hour_hist[h]} for h in range(24)],
        "byWeekday": [{"label": WEEKDAY_CN[i], "orders": weekday_hist[i]} for i in range(7)],
    }


def _calc_items(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not lines:
        return {"top": [], "distinctCount": 0, "totalCount": 0, "unmatchedCount": 0,
                "topKcal": [], "loyaltyRate": 0.0}

    qty_counter: Counter = Counter()
    order_counter: Dict[str, set] = defaultdict(set)
    kcal_counter: Counter = Counter()
    total_units = 0
    unmatched = 0
    for line in lines:
        qty_counter[line["name"]] += line["qty"]
        kcal_counter[line["name"]] += line["energyKcal"]
        order_counter[line["name"]].add(line["orderId"])
        total_units += line["qty"]
        if not line["matched"]:
            unmatched += 1

    top = [
        {
            "name": name,
            "qty": qty,
            "orders": len(order_counter[name]),
            "kcal": round(kcal_counter[name], 1),
        }
        for name, qty in qty_counter.most_common(10)
    ]
    top_kcal = [
        {"name": name, "kcal": round(kcal, 1)}
        for name, kcal in kcal_counter.most_common(8)
    ]

    # 口味忠诚度：被点过 2 次以上的商品种数 / 商品总种数
    repeat_kinds = sum(1 for q in qty_counter.values() if q > 1)
    return {
        "top": top,
        "topKcal": top_kcal,
        "distinctCount": len(qty_counter),
        "totalCount": total_units,
        "unmatchedCount": unmatched,
        "repeatKindCount": repeat_kinds,
        "loyaltyRate": round(repeat_kinds / len(qty_counter) * 100, 1) if qty_counter else 0.0,
    }


def _calc_nutrition(lines: List[Dict[str, Any]], nutrition: NutritionIndex) -> Dict[str, Any]:
    totals = {f: round(sum(l[f] for l in lines), 1) for f in NutritionIndex.FIELDS}
    order_ids = {l["orderId"] for l in lines if l.get("orderId")}
    per_order = round(totals["energyKcal"] / len(order_ids), 1) if order_ids else 0.0
    per_order_sodium = round(totals["sodium"] / len(order_ids), 1) if order_ids else 0.0

    macro = totals["protein"] + totals["fat"] + totals["carbohydrate"]
    macro = macro or 1.0
    return {
        **totals,
        "perOrderKcal": per_order,
        "perOrderSodium": per_order_sodium,
        "macroSplit": {
            "protein": round(totals["protein"] / macro * 100, 1),
            "fat": round(totals["fat"] / macro * 100, 1),
            "carbohydrate": round(totals["carbohydrate"] / macro * 100, 1),
        },
        "bigMacEquivalent": round(totals["energyKcal"] / BIG_MAC_KCAL, 1),
        "riceBowlEquivalent": round(totals["energyKcal"] / RICE_BOWL_KCAL, 1),
        "runKmEquivalent": round(totals["energyKcal"] / RUN_KCAL_PER_KM, 1),
        "sodiumVsDaily": round(totals["sodium"] / DAILY_SODIUM_MG, 2),
        "perOrderVsMealRef": round(per_order / MEAL_KCAL_REF, 2),
        "nutritionTableSize": len(nutrition.table),
        "matchedLineRatio": round(
            sum(1 for l in lines if l["matched"]) / len(lines) * 100, 1
        ) if lines else 0.0,
    }


def _calc_points(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {"available": 0.0, "accumulative": 0.0, "expired": 0.0,
                "expiringThisMonth": 0.0, "nextMonthExpire": 0.0, "sleeping": 0.0, "hasData": False}
    available = _num(data.get("availablePoint"))
    accumulative = _num(data.get("accumulativePoint"))
    expired = _num(data.get("expiredPoint"))
    expiring = _num(data.get("currentMouthExpirePoint"))
    next_expire = _num(data.get("nextMouthExpirePoint"))
    return {
        "available": available,
        "accumulative": accumulative,
        "expired": expired,
        "expiringThisMonth": expiring,
        "nextMonthExpire": next_expire,
        "sleeping": expired + expiring,
        "hasData": True,
    }


def _calc_wallet(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    owned = _as_list(raw.get("query-my-coupons", {}).get("data"), "list", "coupons")
    claimable = _as_list(raw.get("available-coupons", {}).get("data"), "list", "coupons")
    prizes = _as_list(raw.get("query-my-prizes", {}).get("data"), "prizes", "list")
    lottery = raw.get("query-lottery-info", {}).get("data") or {}
    mall_pages = _as_list(raw.get("mall-order-list", {}).get("data"), "list")
    mall_orders = 0
    if mall_pages:
        if isinstance(mall_pages[0], dict) and "list" in mall_pages[0]:
            mall_orders = sum(len(_as_list(p.get("list"))) for p in mall_pages if isinstance(p, dict))
        else:
            mall_orders = len(mall_pages)
    return {
        "ownedCoupons": len(owned),
        "claimableCoupons": len(claimable),
        "claimableNames": [
            str(c.get("title") or c.get("name") or "").strip()
            for c in claimable if isinstance(c, dict)
        ][:8],
        "lotteryPrizes": len(_as_list(lottery.get("prizes"), "list")) if isinstance(lottery, dict) else 0,
        "lotteryPoint": _num(lottery.get("drawPoint")) if isinstance(lottery, dict) else 0.0,
        "prizes": len(prizes),
        "mallOrders": mall_orders,
    }


# ------------------------------------------------------------------ 结论卡片

LEVEL_ORDER = {"warn": 3, "info": 2, "good": 1}


def _calc_verdicts(overview, trends, items, nutrition, points, wallet) -> List[Dict[str, str]]:
    cards: List[Dict[str, Any]] = []

    if overview["orderCount"] == 0:
        cards.append({
            "level": "info",
            "tag": "空号提示",
            "title": "这个账号还没有历史订单",
            "desc": "体检报告依赖历史订单数据。当前 MCP Token 对应的账号暂无订单记录，"
                    "可以先跑 `--sample` 看演示效果，或换一个有消费记录的账号再试。",
        })
    else:
        # 深夜食堂指数
        night = sum(b["orders"] for b in trends["byHour"] if b["hour"] >= 22 or b["hour"] < 5)
        ratio = night / overview["orderCount"] * 100
        level = "warn" if ratio >= 20 else ("info" if ratio >= 8 else "good")
        cards.append({
            "level": level,
            "tag": "深夜食堂指数",
            "title": "%.0f%% 的单下在深夜（22:00-05:00）" % ratio,
            "desc": "共 %d 单夜宵。" % night if night
                    else "作息很健康，没有深夜点单记录。",
        })

        # 招牌单品
        if items["top"]:
            top = items["top"][0]
            cards.append({
                "level": "info",
                "tag": "本命单品",
                "title": "%s 是你点得最多的（%d 件）" % (top["name"], top["qty"]),
                "desc": "点过 %d 种商品，其中 %.0f%% 重复下单；它占全部件数的 %.1f%%。"
                        % (items["distinctCount"], items["loyaltyRate"],
                           top["qty"] / max(1, items["totalCount"]) * 100),
            })

        # 钠摄入
        if nutrition["perOrderSodium"] > 0:
            level = "warn" if nutrition["perOrderSodium"] >= DAILY_SODIUM_MG else "info"
            cards.append({
                "level": level,
                "tag": "钠超标预警",
                "title": "平均每单摄入 %.0f mg 钠" % nutrition["perOrderSodium"],
                "desc": "相当于每日推荐上限的 %.0f%%。累计 %d mg，建议搭配无糖饮品和低钠小食。"
                        % (nutrition["perOrderSodium"] / DAILY_SODIUM_MG * 100, nutrition["sodium"]),
            })

        # 热量
        if nutrition["perOrderKcal"] > 0:
            level = "warn" if nutrition["perOrderKcal"] >= 1.3 * MEAL_KCAL_REF else (
                "good" if nutrition["perOrderKcal"] <= MEAL_KCAL_REF else "info")
            cards.append({
                "level": level,
                "tag": "热量账单",
                "title": "平均每单 %.0f kcal" % nutrition["perOrderKcal"],
                "desc": "累计 %.0f kcal ≈ %.1f 个巨无霸，需要慢跑 %.1f 公里才能抵消。"
                        % (nutrition["energyKcal"], nutrition["bigMacEquivalent"],
                           nutrition["runKmEquivalent"]),
            })

        # 忠实门店
        if overview["topStore"]:
            share = overview["topStoreCount"] / overview["orderCount"] * 100
            cards.append({
                "level": "info" if share < 70 else "good",
                "tag": "据点",
                "title": "%s 贡献了 %.0f%% 的订单" % (overview["topStore"], share),
                "desc": "共 %d 单。可在配 Address 后估算通勤距离与取餐便利度。"
                        % overview["topStoreCount"],
            })

        # 客单价
        cards.append({
            "level": "info",
            "tag": "钱包体感",
            "title": "客单价 ¥%.2f" % overview["avgTicket"],
            "desc": "累计消费 ¥%.2f，跨越 %d 天。"
                    % (overview["totalSpend"], overview["spanDays"]),
        })

    # 积分（有没有订单都给）
    if points.get("hasData"):
        if points["sleeping"] > 0:
            cards.append({
                "level": "warn",
                "tag": "沉睡积分",
                "title": "%.1f 积分已经过期或本月将过期" % points["sleeping"],
                "desc": "可用 %.1f / 累计 %.1f。积分是有保质期的，别让它躺过期。"
                        % (points["available"], points["accumulative"]),
            })
        elif points["available"] > 0:
            cards.append({
                "level": "good",
                "tag": "积分健康",
                "title": "账上有 %.1f 可用积分" % points["available"],
                "desc": "累计 %.1f 积分，暂无过期损耗。" % points["accumulative"],
            })

    names_preview = "、".join([n for n in wallet["claimableNames"][:4] if n])
    if wallet.get("claimableCoupons"):
        cards.append({
            "level": "info",
            "tag": "漏领的羊毛",
            "title": "还有 %d 张券可以领" % wallet["claimableCoupons"],
            "desc": names_preview or "打开麦当劳 MCP 查询可领取的优惠券即可查看。",
        })

    cards.sort(key=lambda c: LEVEL_ORDER.get(c["level"], 0), reverse=True)
    return cards
