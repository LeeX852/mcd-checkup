#!/usr/bin/env python3
"""生成演示用的原始数据 `assets/sample-raw.json`。

为什么要它：
    参赛仓库必须能在「没有 Token、没有历史订单」的评委机器上直接跑出效果，
    否则 README 里的截图只能靠嘴说。--sample 走的和 live 完全同一条分析链路，
    只是喂一份脱敏的构造数据。

    其中营养表用的是麦当劳 MCP 真实返回的 160 条餐品营养数据（公开信息），
    订单/积分/券部分是构造的，不含任何真实个人信息。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NUTRITION_FILE = os.path.join(ROOT, "assets", "nutrition-table.txt")
OUT_FILE = os.path.join(ROOT, "assets", "sample-raw.json")

STORES = ["麦当劳（科技园店）", "麦当劳（中山路餐厅）", "麦当劳（万象城得来速店）",
          "麦当劳（滨江道 DT 店）", "麦当劳（大学城店）"]
PRODUCTS = [
    "巨无霸", "麦辣鸡腿汉堡", "板烧鸡腿堡", "双层吉士汉堡", "麦香鱼",
    "中薯条", "大薯条", "麦乐鸡5块", "麦乐鸡4块", "那么大鸡排",
    "麦辣鸡翅-2块", "麦旋风奥利奥", "草莓麦旋风", "圆筒冰淇淋",
    "可乐中杯", "无糖可口可乐中杯", "冰美式中杯", "热牛奶中杯", "纯悦",
    "脆薯饼", "苹果片", "大杯玉米杯", "优品豆浆大杯", "脆香油条",
]
WEIGHTS = [12, 10, 9, 6, 4, 14, 7, 9, 6, 3, 4, 5, 4, 6, 8, 7, 6, 3, 5, 5, 3, 2, 3, 3]
ORDER_TYPES = ["外卖", "到店取餐", "得来速", "堂食"]


def build(seed: int = 1024, orders: int = 46, days: int = 240) -> dict:
    rng = random.Random(seed)
    today = dt.date(2026, 10, 11)
    rows = []

    for i in range(orders):
        day = today - dt.timedelta(days=rng.randint(0, days))
        # 工作日中午和晚饭后是高峰，深夜加点单
        roll = rng.random()
        if roll < 0.42:
            hour = rng.choice([11, 11, 12, 12, 12, 13, 13])
        elif roll < 0.78:
            hour = rng.choice([18, 18, 19, 19, 20])
        elif roll < 0.92:
            hour = rng.choice([15, 16, 17])
        else:
            hour = rng.choice([22, 23, 23])
        minute = rng.randint(0, 59)

        picked = rng.choices(PRODUCTS, weights=WEIGHTS, k=rng.randint(1, 3))
        items = []
        for name in picked:
            qty = rng.choice([1, 1, 1, 1, 2])
            items.append(
                {
                    "productCode": "P%04d" % rng.randint(1000, 9999),
                    "productName": name,
                    "quantity": qty,
                    "comboItemList": [],
                }
            )
        # 单价按品类量级构造，让客单价落在真实区间（¥18–¥45）
        unit = round(rng.uniform(8.0, 24.0), 2)
        amount = round(unit * sum(it["quantity"] for it in items), 2)
        rows.append(
            {
                "orderId": "SN%013d" % rng.randint(10 ** 11, 10 ** 12 - 1),
                "orderType": rng.choice(ORDER_TYPES),
                "createTime": "%s %02d:%02d:%02d" % (day.isoformat(), hour, minute, rng.randint(0, 59)),
                "beType": rng.choice(["DT", "STORE", "MC_CAFE"]),
                "beCode": "BE%04d" % rng.randint(100, 999),
                "storeCode": "S%04d" % rng.randint(1000, 9999),
                "storeName": rng.choice(STORES),
                "orderStatus": "已完成",
                "orderProductList": items,
                "realTotalAmount": "%.2f" % amount,
            }
        )

    with open(NUTRITION_FILE, encoding="utf-8") as fh:
        nutrition = fh.read()

    return {
        "order-list": {
            "data": {"list": rows},
            "text": "sample",
            "isError": False,
        },
        "list-nutrition-foods": {
            "data": nutrition,
            "text": "sample",
            "isError": False,
        },
        "query-my-account": {
            "data": {
                "accountId": "SAMPLE-ACCOUNT",
                "accumulativePoint": "1268.5",
                "availablePoint": "47.5",
                "currency": "麦享会积分",
                "currentMouthExpirePoint": "120.0",
                "expiredPoint": "89.0",
                "frozenPoint": "0",
                "lastMouthExpirePoint": "0",
                "nextMouthExpirePoint": "0",
                "usedPoint": "1032.0",
            },
            "text": "sample",
            "isError": False,
        },
        "query-my-coupons": {
            "data": {"list": [{"title": "中薯条买一送一", "status": "未使用"},
                              {"title": "麦旋风5折券", "status": "未使用"}]},
            "text": "sample",
            "isError": False,
        },
        "available-coupons": {
            "data": {"list": [
                {"title": "中薯条买一送一", "status": "可领取"},
                {"title": "王牌小食拼", "status": "可领取"},
                {"title": "免费脆薯饼", "status": "可领取"},
                {"title": "9.9元中杯冰美式", "status": "可领取"},
            ]},
            "text": "sample",
            "isError": False,
        },
        "query-lottery-info": {
            "data": {"drawPoint": "24", "activityStatusText": "进行中", "prizes": []},
            "text": "sample",
            "isError": False,
        },
        "query-my-prizes": {"data": {"prizes": []}, "text": "sample", "isError": False},
        "mall-order-list": {"data": [{"hasNext": False, "lastId": 0, "list": []}],
                            "text": "sample", "isError": False},
        "campaign-calendar": {"data": {}, "text": "sample", "isError": False},
        "now-time-info": {"data": {"formatted": today.isoformat() + " 12:00:00"},
                          "text": "sample", "isError": False},
    }


def main() -> int:
    raw = build()
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=2)
    print("已生成 %s（%d 个演示订单，营养表 %s 行）"
          % (OUT_FILE, len(raw["order-list"]["data"]["list"]), "160"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
