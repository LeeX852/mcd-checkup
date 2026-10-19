# 麦当劳 MCP Server 集成说明

本文档说明「麦麦体检报告」实际调用了哪些麦当劳 MCP Server 的工具、调用流程与业务价值。
对应代码：`scripts/mcd_mcp.py`（客户端）、`scripts/checkup.py`（抓数流程）、`scripts/analyze.py`（计算）。

## 一、接入方式

| 项 | 值 |
|---|---|
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 认证 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| 会话流程 | `initialize` → `notifications/initialized` → `tools/call` |
| 限流 | 每 Token 每分钟 600 次（本工具全程约 10 次调用，远低于限额） |
| 依赖 | Python 3.9+，纯标准库，无第三方包 |

客户端实现要点：

- `mcd_mcp.py` 用 `urllib` 手写 JSON-RPC 2.0，兼容服务端返回 **纯 JSON** 与 **SSE** 两种形态；
- 对 TLS 握手被中断、连接重置等网络抖动做 3 次退避重试，单个工具失败不会让整轮崩掉；
- 结果归一化：优先取 `structuredContent`，退化时从 `content[0].text` 尾部的
  `## Original Response` 段里抠 JSON，最后兜底纯文本。

## 二、实际调用的 Tool

全部为**只读**工具，共 10 个。客户端内置白名单，任何写操作（下单、领券、抽奖、取消订单）
会被直接拒绝。

| Tool | 用途 | 用于报告的哪个模块 |
|---|---|---|
| `list-nutrition-foods` | 餐品营养信息列表 | 营养表。返回 160 条餐品的能量/蛋白质/脂肪/碳水/钠/钙，是所有热量计算的基准 |
| `order-list` | 历史订单（到店/外送） | 消费总览、月度节奏、24 小时节律、一周分布、本命单品 TOP10、门店榜单 |
| `query-my-account` | 积分账户 | 积分账本：可用/累计/已用/已过期/本月将过期/下月将过期 |
| `query-my-coupons` | 我的优惠券 | 钱包：持有券数量 |
| `available-coupons` | 可领取的优惠券 | 「还没领的羊毛」结论卡 |
| `query-lottery-info` | 积分抽奖活动 | 钱包：奖池项数、单次消耗积分 |
| `query-my-prizes` | 抽奖奖品记录 | 钱包：已中奖品数 |
| `mall-order-list` | 麦麦商城订单 | 钱包：商城订单数 |
| `campaign-calendar` | 活动日历 | 当月活动上下文 |
| `now-time-info` | 当前时间 | 报告生成时间戳 |

## 三、调用流程

```
checkup.py
   └── McdMcp.initialize()                  # 握手，拿 protocolVersion / serverInfo
        └── for tool in READ_ONLY_TOOLS:    # 10 个只读工具
             └── McdMcp.call(tool)          # tools/call，异常降级不中断
                  └── _unwrap()             # structuredContent → text 抠 JSON → 纯文本
   └── analyze.build_report(raw)            # 拍平订单 → 匹配营养 → 算指标 → 出结论卡
        └── persona.derive_persona()        # 同一份指标 → 画像（不额外调 MCP）
   └── report.json
        ├── render.py                       # 注入 app/index.html → 单文件报告
        └── card.build_card() → card.json   # 五张卡面 + 主题 + 品质
             └── render.py                  # 注入 app/card.html → 单文件卡片页 → 导出 PNG
```

### 订单与营养的匹配链路（核心难点）

`order-list` 返回的商品名是**下单口径**（含规格、温度、组合），
`list-nutrition-foods` 返回的是**餐品口径**，两者不能直接 join。
`analyze.NutritionIndex` 做四级匹配：

1. 原名精确匹配
2. 去掉括号规格后的清洗名精确匹配（`可乐(中杯)` → `可乐中杯`）
3. 包含匹配：营养表名是商品名的子串，取最长命中
4. 模糊兜底：编辑距离相似度 + 中文二元字组重合度（应对「麦旋风奥利奥」↔「奥利奥麦旋风」这类倒装名）

套餐商品（有 `comboItemList`）在商品名匹配失败时，改为累加子项营养。
实测 110 条商品行匹配率 **100%**（演示数据），未匹配项会在报告「钱包与商城」卡片里显式披露。

## 四、业务价值

- **把散落的接口变成一份能看懂的结论。** 单看 `order-list` 只是流水账；
  叠加营养表和积分账户后，能回答「我这一年到底吃了多少热量、攒了多少没用的积分」。
- **跨域关联才有信息增量。** 热量 × 订单 = 热量账单；积分 × 过期时间 = 沉睡积分预警；
  券 × 订单 = 漏领的羊毛。单工具都做不到。
- **同一份数据二次表达，换来传播。** 角色卡不新增任何 MCP 调用，只把已算好的指标翻译成
  称号、五维、稀有度和外观参数——用零额外请求，把「看完就关」的报告变成「截图发群」的卡片。
  这是只读数据的复用率上限：一次抓数，两种产物。
- **可视化自带传播。** 单文件 HTML 报告与卡片页都零依赖、可托管，截图即可分享。

### 角色卡复用了哪些字段

| 卡面元素 | 数据来源（MCP 工具 → 报告字段） |
|---|---|
| 稀有度 / 五维 | `order-list` → 订单数、件数、消费额、复购率、种类数；`byHour` → 深夜占比 |
| 沉睡积分（决定「沉睡财主」原型） | `query-my-account` → `expiredPoint + currentMouthExpirePoint` |
| 钱包卡 | `query-my-coupons` / `available-coupons` / `query-lottery-info` / `query-my-prizes` / `mall-order-list` |
| 战绩卡热量账单 | `list-nutrition-foods` × `order-list` → 累计热量、巨无霸等价、慢跑公里、钠 |
| 节律卡的常去门店 | `order-list` → `storeName` 频次 |
| 卡号 / 生成时间 | `now-time-info` + 账号指纹（首末订单日期等） |

## 五、安全与合规

- 全程只读，不产生任何写操作，用户账户零风险。
- Token 只从环境变量 `MCD_MCP_TOKEN` 读取，不写入仓库、日志或报告；
  仓库内只保留 `mcp-config.example.json` 这样的环境变量占位符。
- 报告不含他人个人信息；演示数据（`assets/sample-raw.json`）为构造数据，
  其中的营养表取自 MCP 公开返回的餐品营养数据。
