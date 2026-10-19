---
name: mcd-checkup
description: 麦麦体检报告 + 麦麦角色卡。把麦当劳账号的历史订单、积分、优惠券、餐品营养数据汇总成一份可分享的可视化体检报告，并基于同一份画像自动生成专属角色卡（含蓝/绿/紫/金/红五档稀有度光晕、五种卡面、五套主题，可导出 PNG 分享）。触发词：麦麦体检、麦当劳消费报告、麦当劳年度报告、我的麦当劳账单、麦麦复盘、麦麦角色卡、我的麦当劳人设、麦当劳抽卡。
---

# 麦麦体检报告（mcd-checkup）

把「我这一年在麦当劳花了多少钱、吃了多少热量、攒了多少没用的积分」变成一份一眼看懂的体检报告，
再把它压成一张能发群的角色卡。

## 何时使用

- 用户想看自己的麦当劳消费复盘 / 年度报告 / 账单分析
- 用户问「我在麦当劳花了多少钱」「我的积分还能不能用」「我点的最多的是什么」
- 用户要一份能发朋友圈的麦当劳数据报告
- 用户想要「我的麦当劳人设 / 角色卡 / 抽卡」——同一份画像会产出带稀有度光晕的卡片

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

脚本会依次调用 10 个**只读** MCP 工具（见 MCP_INTEGRATION.md），产出两份数据：

- `report.json`：结构化报告
- `card.json`：角色卡数据（画像 + 五张卡面 + 主题 + 品质阶梯）
- `report.raw.json`（加 `--dump-raw` 时）：原始抓取，便于排查

### 第 2 步：渲染两个单文件页面

```bash
python scripts/render.py --data report.json --out report.html --card-out card.html
```

不带 `--data` 则用演示数据打包，同时生成 `preview.html` 与 `card.html`。

| 产物 | 说明 |
|---|---|
| `report.html` | 体检报告，零外部依赖、双击即开；顶部有「角色卡」入口 |
| `card.html` | **独立卡片页**，五张卡面可切换、五套主题可切换、一键导出 PNG |

### 第 3 步：向用户汇报

只报结论，不要复述全表。重点讲这几项：

1. 累计消费、客单价、统计跨度
2. 累计热量及等价物（多少个巨无霸 / 多少公里慢跑）
3. **深夜食堂指数**（22:00–05:00 下单占比）和**钠摄入**是否超每日推荐上限
4. 本命单品 TOP3
5. **沉睡积分**（已过期 + 本月将过期）——这项最容易让人有行动欲
6. 还没领的券
7. **角色卡结论**：角色名 + 称号 + 稀有度 + 战力，并提示「打开 card.html 可换主题、导图分享」

## 角色卡（本 Skill 的第二个产物）

同一份 `report.json`，多一层叙事：数据决定人设。

| 维度 | 内容 |
|---|---|
| 五张卡面 | 角色卡（圆形立绘窗 + 五维 + 战力徽章）/ 战绩卡（消费 + 本命）/ 节律卡（24h + 一周）/ 钱包卡（积分损耗）/ 徽章卡（10 枚成就） |
| 五套主题 | 经典红黄 / 深夜电波 / 手账米白 / 赛博荧光 / 金箔典藏，随画像自动匹配，可手动切换 |
| 五档品质 | 蓝 → 绿 → 紫 → 金 → 红，按战力 0 / 40 / 56 / 72 / 87 划档，卡面四周按品质渲染不同强度的光晕 |
| 导出 | 画布 1080×1512，导出 2160×3024 PNG（2 倍图），文件名带卡面与品质 |

完整规则（五维公式、原型判定、内容构成、光晕实现、导出规格）见 [CARD_DESIGN.md](CARD_DESIGN.md)。

## 硬性约束

- **只调用只读工具。** 脚本内置白名单（`scripts/mcd_mcp.py` 的 `READ_ONLY_TOOLS`），
  任何写操作（`create-order` / `auto-bind-coupons` / `draw-lottery` / `cancel-order` 等）一律拒绝。
- **Token 不落盘。** 只从环境变量 `MCD_MCP_TOKEN` 读；不要把 Token 写进任何文件、
  日志或命令行历史。
- **角色卡不增加 MCP 调用。** 画像全部由已有指标派生，Token 消耗与限流风险不变。
- **角色必须可复现。** 外观与稀有度由账号指纹播种，同一账号重跑结果一致；
  不要为了让卡片"好看"而手改稀有度或外观（演示可临时切，但不写入数据）。
- **立绘是仓库内固定素材。** `assets/characters/` 的 8 张原型立绘在构建期按画像取一张内联，
  运行时不出图、不联网、不上传数据；素材缺失时自动退回程序化角色，卡片仍可生成。
- 用户没有历史订单时，明确告知「当前账号暂无订单」，并引导用 `--sample` 看效果，
  不要编造数据；此时角色会落到「麦麦新客 · 蓝色品质」，属于正常结果。
- 报告结论仅供参考，不构成医疗、营养建议；角色形象为原创卡通绘制，不使用官方吉祥物。

## 目录结构

```
mcd-checkup/
├── SKILL.md                  # 本文件
├── README.md                 # 项目介绍 / 安装 / 使用示例 / 目标用户
├── CARD_DESIGN.md            # 角色卡设计说明（衔接方式 / 卡面 / 品质 / 导出）
├── CONTEST_DECLARATION.md    # 参赛声明（官方原文，不可改动）
├── MCP_INTEGRATION.md        # MCP 工具清单与调用流程
├── mcp-config.example.json   # 脱敏配置示例（仅环境变量占位符）
├── workbuddy.md              # WorkBuddy 对话上下文
├── preview.html              # 内嵌演示数据的成品报告
├── card.html                 # 内嵌演示数据的成品角色卡（可导图）
├── scripts/
│   ├── mcd_mcp.py            # MCP JSON-RPC 客户端（Streamable HTTP，含重试）
│   ├── analyze.py            # 指标计算：营养匹配、趋势、结论卡片
│   ├── persona.py            # 画像推导：五维 / 稀有度 / 原型 / 外观 / 徽章
│   ├── card.py               # 卡面数据构建：五张卡 × 五套主题
│   ├── checkup.py            # 主流程 CLI
│   ├── make_sample.py        # 生成演示数据
│   └── render.py             # 打包两个单文件页面
├── app/
│   ├── index.html            # 报告界面模板（数据由 render.py 注入）
│   └── card.html             # 卡片页模板（Canvas 绘制 + PNG 导出）
└── assets/
    ├── characters/           # 8 张原型立绘 + manifest.json（构建期内联）
    ├── nutrition-table.txt   # 麦当劳餐品营养数据（MCP 真实返回，160 条）
    └── sample-raw.json       # 脱敏演示数据
```
