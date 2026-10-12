---
name: mcd-checkup
description: 麦麦体检报告。把麦当劳账号的历史订单、积分、优惠券、餐品营养数据汇总成一份可分享的可视化体检报告，输出「累计消费 / 客单价 / 累计热量 / 钠摄入 / 深夜食堂指数 / 本命单品 / 沉睡积分」等结论。触发词：麦麦体检、麦当劳消费报告、麦当劳年度报告、我的麦当劳账单、麦麦复盘。
---

# 麦麦体检报告（mcd-checkup）

把「我这一年在麦当劳花了多少钱、吃了多少热量、攒了多少没用的积分」变成一份一眼看懂的体检报告。

## 何时使用

- 用户想看自己的麦当劳消费复盘 / 年度报告 / 账单分析
- 用户问「我在麦当劳花了多少钱」「我的积分还能不能用」「我点的最多的是什么」
- 用户要一份能发朋友圈的麦当劳数据报告

## 前置条件

1. 已配置麦当劳 MCP 连接器（`mcd-mcp`，地址 `https://mcp.mcd.cn`，Streamable HTTP）。
   Token 从麦当劳 MCP 开放平台申请：https://open.mcd.cn/mcp
2. Python 3.9+，**零第三方依赖**（纯标准库）。

## 工作流

### 第 1 步：抓数 + 分析

```bash
# 真实数据（需要 MCD_MCP_TOKEN）
export MCD_MCP_TOKEN="你的Token"
python scripts/checkup.py --out report.json --dump-raw

# 没有 Token 或账号没有订单时，用内置演示数据
python scripts/checkup.py --sample --out report.json
```

脚本会依次调用 10 个**只读** MCP 工具（见 MCP_INTEGRATION.md），把原始结果写成
`report.json`（结构化报告）和 `report.raw.json`（原始抓取，便于排查）。

### 第 2 步：渲染单文件报告

```bash
python scripts/render.py --data report.json --out report.html
```

产物 `report.html` 是零外部依赖的单文件：数据内联、不发任何网络请求，
双击可看，也可直接托管。不带 `--data` 则用演示数据打包。

### 第 3 步：向用户汇报

只报结论，不要复述全表。重点讲这几项：

1. 累计消费、客单价、统计跨度
2. 累计热量及等价物（多少个巨无霸 / 多少公里慢跑）
3. **深夜食堂指数**（22:00–05:00 下单占比）和**钠摄入**是否超每日推荐上限
4. 本命单品 TOP3
5. **沉睡积分**（已过期 + 本月将过期）——这项最容易让人有行动欲
6. 还没领的券

## 硬性约束

- **只调用只读工具。** 脚本内置白名单（`scripts/mcd_mcp.py` 的 `READ_ONLY_TOOLS`），
  任何写操作（`create-order` / `auto-bind-coupons` / `draw-lottery` / `cancel-order` 等）一律拒绝。
- **Token 不落盘。** 只从环境变量 `MCD_MCP_TOKEN` 读；不要把 Token 写进任何文件、
  日志或命令行历史。
- 用户没有历史订单时，明确告知「当前账号暂无订单」，并引导用 `--sample` 看效果，
  不要编造数据。
- 报告结论仅供参考，不构成医疗、营养建议。

## 目录结构

```
mcd-checkup/
├── SKILL.md                  # 本文件
├── README.md                 # 项目介绍 / 安装 / 使用示例 / 目标用户
├── CONTEST_DECLARATION.md    # 参赛声明（官方原文，不可改动）
├── MCP_INTEGRATION.md        # MCP 工具清单与调用流程
├── mcp-config.example.json   # 脱敏配置示例（仅环境变量占位符）
├── workbuddy.md              # WorkBuddy 对话上下文
├── preview.html              # 内嵌演示数据的成品报告
├── scripts/
│   ├── mcd_mcp.py            # MCP JSON-RPC 客户端（Streamable HTTP，含重试）
│   ├── analyze.py            # 指标计算：营养匹配、趋势、结论卡片
│   ├── checkup.py            # 主流程 CLI
│   ├── make_sample.py        # 生成演示数据
│   └── render.py             # 打包单文件 HTML
├── app/index.html            # 报告界面模板（数据由 render.py 注入）
└── assets/
    ├── nutrition-table.txt   # 麦当劳餐品营养数据（MCP 真实返回，160 条）
    └── sample-raw.json       # 脱敏演示数据
```
