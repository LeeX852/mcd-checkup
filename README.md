# 🍔 麦麦体检报告 · mcd-checkup

> 你在麦当劳花了多少钱、吃了多少热量、攒了多少没用的积分？一条命令，生成一份能发朋友圈的体检报告。

基于 **麦当劳 MCP Server** 的只读能力，把历史订单、积分账户、优惠券、餐品营养四类数据打通，
算出一份带结论的可视化体检报告。**纯 Python 标准库，零第三方依赖；产物是单文件 HTML，双击即开。**

![报告预览](screenshots/hero.png)

---

## 为什么做这个

麦当劳 MCP 提供了 35 个工具，但单看 `order-list` 只是一串流水账——知道"买了什么"，不知道"这意味着什么"。

这个 Skill 做的事情很简单：**把散落的接口数据交叉起来，回答三个问题。**

| 问题 | 用到的 MCP 工具 | 产出结论 |
|---|---|---|
| 我这一年到底吃了多少？ | `order-list` × `list-nutrition-foods` | 累计热量 ≈ 多少个巨无霸 / 要慢跑多少公里；钠摄入是否超每日推荐上限 |
| 我的钱花得值吗？ | `order-list` × `query-my-account` | 客单价、月度节奏、24 小时下单节律、本命单品 TOP10 |
| 有什么我白白浪费了？ | `query-my-account` × `available-coupons` | 沉睡积分预警、还没领的券 |

## 快速开始

### 方式一：命令行（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/<你的账号>/mcd-checkup.git
cd mcd-checkup

# 2. 配置 MCP Token（从 https://open.mcd.cn/mcp 申请）
export MCD_MCP_TOKEN="你的MCP_TOKEN"

# 3. 抓数 + 分析
python scripts/checkup.py --out report.json

# 4. 渲染单文件报告
python scripts/render.py --data report.json --out report.html
```

打开 `report.html` 即可。**没有 Token 也能跑：**

```bash
python scripts/checkup.py --sample --out report.json   # 用内置演示数据
python scripts/render.py                                # 直接打包演示版
```

### 方式二：作为 WorkBuddy Skill 使用

把本仓库放进 Skill 目录，然后在对话里直接说：

> 「帮我做一份麦麦体检报告」

Skill 会自动抓数、分析，并只汇报关键结论（深夜食堂指数、沉睡积分、本命单品……）。
详见 [SKILL.md](SKILL.md)。

## 报告里有什么

| 模块 | 内容 |
|---|---|
| 体检结论 | 按严重程度排序的结论卡：深夜食堂指数、钠超标预警、本命单品、沉睡积分、漏领的羊毛…… |
| 核心指标 | 累计消费 / 订单数 / 客单价 / 累计热量 / 累计钠 / 可用积分 |
| 月度消费节奏 | 按月消费柱状图 |
| 24 小时下单节律 | 按小时分布，深夜时段（22:00–05:00）单独标色 |
| 一周分布 | 周几最勤 |
| 营养素构成 | 蛋白质 / 脂肪 / 碳水占比环形图 + 平均每单热量与钠 |
| 本命单品 TOP10 | 件数、下单次数、累计热量、占比条 |
| 积分账本 | 可用 / 累计 / 已用 / 已过期 / 本月将过期 / 下月将过期 |
| 钱包与商城 | 持有券、可领券、抽奖奖池、商城订单、营养表匹配率 |

报告页支持**拖入 `report.json`** 查看自己的数据、一键**复制文字版**（适合发群）。

## 目标用户

- **想复盘自己麦当劳消费的人**——尤其是办了麦金卡、攒了一堆积分不知道用没用的人
- **健身 / 控卡人群**——需要知道"这顿麦满分顶几碗米饭"
- **想快速理解麦当劳 MCP 能干什么的开发者**——10 个只读工具串成一条完整数据链路的参考实现
- **参赛评委**——仓库自带演示数据与成品报告，无需 Token 即可查看效果

## 目录结构

```
mcd-checkup/
├── SKILL.md                  # Skill 定义（触发词 + 工作流 + 硬性约束）
├── README.md                 # 本文件
├── CONTEST_DECLARATION.md    # 参赛声明（官方原文，不可改动）
├── MCP_INTEGRATION.md        # 调用了哪些 Tool、调用流程、业务价值
├── mcp-config.example.json   # 脱敏 MCP 配置（仅环境变量占位符）
├── workbuddy.md              # WorkBuddy 对话上下文
├── preview.html              # 内嵌演示数据的成品报告，双击可看
├── scripts/
│   ├── mcd_mcp.py            # MCP JSON-RPC 客户端（Streamable HTTP，含重试）
│   ├── analyze.py            # 指标计算：营养匹配、趋势、结论卡
│   ├── checkup.py            # 主流程 CLI
│   ├── make_sample.py        # 生成演示数据
│   └── render.py             # 打包单文件 HTML
├── app/index.html            # 报告界面模板（数据由 render.py 注入）
├── assets/
│   ├── nutrition-table.txt   # 麦当劳餐品营养数据（MCP 真实返回，160 条）
│   └── sample-raw.json       # 脱敏演示数据
└── screenshots/
```

## 安全设计

| 项 | 做法 |
|---|---|
| 只读 | 客户端内置 `READ_ONLY_TOOLS` 白名单，`create-order` / `auto-bind-coupons` / `draw-lottery` / `cancel-order` 等写操作**直接拒绝**，账户零风险 |
| Token | 只从环境变量 `MCD_MCP_TOKEN` 读取，不写入仓库、日志、报告；仓库内只有 `${MCD_MCP_TOKEN}` 占位符 |
| 隐私 | 报告不含他人个人信息；演示数据为构造数据 |

## 已知限制

- 营养匹配依赖 `list-nutrition-foods` 的餐品名与订单商品名对齐，四级匹配后仍有极少数名称对不上；
  未匹配数量会在报告里显式披露，不会静默算错。
- `order-list` 只返回近期订单，跨年度长周期统计受接口分页影响。
- 报告结论仅供参考，**不构成医疗、营养或其他专业建议**；餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准。

## 参赛信息

麦当劳程序员创意开发大赛参赛作品。活动仓库：
<https://github.com/M-China/mcd-developer-innovation-challenge>

本项目为参赛者独立开发，**非麦当劳官方产品**。

## License

[MIT](LICENSE) —— 代码部分自由使用。麦当劳相关名称、商标归其权利人所有。
