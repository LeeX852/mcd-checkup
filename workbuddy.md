# workbuddy.md · WorkBuddy 对话上下文

本文件记录「麦麦体检报告」在 **腾讯 WorkBuddy** 中的开发过程，用于麦当劳程序员创意开发大赛
WorkBuddy 专项奖励的联动核验。开发全程使用 WorkBuddy 的 Agent 模式完成。

- **开发工具**：腾讯 WorkBuddy（Agent 模式）
- **开发周期**：2026-10-12（单日完成从调研到可运行原型）
- **连接器**：WorkBuddy 自定义 MCP 连接器 `mcd-mcp`（`https://mcp.mcd.cn`，Streamable HTTP）
- **是否真实使用 WorkBuddy 智能体**：是。下述每一步均在 WorkBuddy 对话中完成，
  包括 MCP 数据探测、协议调试、代码编写与视觉验收。

---

## 一、需求确认阶段

**输入**：漂泊者提供大赛活动仓库地址
<https://github.com/M-China/mcd-developer-innovation-challenge>，要求参赛。

**WorkBuddy 做的事**：

1. 拉取并通读活动仓库的 `README.md`、`activityGuidelines.md`、`CONTEST_DECLARATION.md`、`RANKING.md`
2. 拉取 MCP Server 文档 <https://github.com/M-China/mcd-mcp-server>，拿到 35 个工具的完整清单与能力边界
3. 拉取 2026-10-12 00:00 的排行榜快照，识别红海赛道与空白赛道

**关键发现**：

- 活动规则两处口径不一致：`README.md` 列的必须文件不含 `mcp-config.example.json`，
  而 `activityGuidelines.md` 要求。按更严的口径执行，避免漏文件被取消资格。
- 榜单 Top4 分别是优惠券策略（93 Star）、派对预约（85）、预算餐（71）、活动雷达（68），
  卡路里/人格测试类也已扎堆。正面撞这些赛道没有胜算。
- 相对空白：**历史订单 × 积分的消费复盘与可视化**。

**结论**：做「麦麦体检报告」——用只读工具把订单、积分、券、营养四类数据交叉，
产出可视化体检报告。差异化强、天然带传播性、且只读实现零账户风险。

## 二、MCP 数据探测阶段

WorkBuddy 通过 `mcd-mcp` 连接器逐个调用只读工具，记录真实返回结构：

| 工具 | 实测结果 |
|---|---|
| `now-time-info` | 返回 200，服务器时间 2026-10-12 00:09:33 |
| `list-nutrition-foods` | 160 条餐品营养（能量/蛋白质/脂肪/碳水/钠/钙），**公开数据，无订单也可用** |
| `query-my-account` | 可用 0 / 累计 91.9 / 已过期 91.9 —— 当前账号是空号 |
| `order-list` | `data.list` 为空数组 |
| `query-my-coupons` | 暂无可用优惠券 |
| `query-lottery-info` | 麦麦积分抽奖进行中，单次 24 积分，10 项奖品 |

**这个阶段发现的核心问题**：当前绑定的账号没有任何历史订单，做不出真实报告。

**决策**：产品必须同时满足两种场景——
(a) 有订单的账号出真实报告；(b) 空号/无 Token 的用户用 `--sample` 演示数据看效果。
后者直接决定评委能不能在 30 秒内看到价值，也决定了 Star 数。

## 三、实现阶段

WorkBuddy 直接编写了全部代码（纯标准库，无第三方依赖）：

| 文件 | 作用 |
|---|---|
| `scripts/mcd_mcp.py` | 手写 JSON-RPC 2.0 客户端，兼容纯 JSON 与 SSE 两种响应形态 |
| `scripts/analyze.py` | 营养表解析、商品名四级匹配、趋势统计、结论卡生成 |
| `scripts/checkup.py` | 主流程 CLI，10 个只读工具串行抓取，单点失败降级不中断 |
| `scripts/make_sample.py` | 生成脱敏演示数据 |
| `scripts/render.py` | 把报告 JSON 注入 HTML 模板，产出单文件 |
| `app/index.html` | 报告界面（深色顶栏 + 白色画布 + 浅灰网格，零依赖手写 SVG 图表） |

**过程中抓到并修掉的 3 个真实 bug**：

1. **`tools/call` 返回被整体拆错** —— 最初把整个 JSON-RPC 信封传给拆包函数，
   `structuredContent` 取不到，10 个工具全部返回空数据。
   修法：`call()` 里先取 `envelope["result"]`。
2. **通知请求解析崩溃** —— `notifications/initialized` 按协议返回 202 空 body，
   解析器把空串当非法响应抛异常。修法：空响应直接返回 `{}`。
3. **商城订单空列表越界** —— `mall[0]` 在空数组上直接 IndexError。修法：先判空再取首元素。

另外针对沙箱内 TLS 握手偶发中断（`SSL: UNEXPECTED_EOF_WHILE_READING`），
给客户端加了 3 次退避重试——真实网络环境下同样有用。

## 四、视觉验收阶段

WorkBuddy 用本机 Edge 无头模式对打包产物截图，逐块放大检查，
发现 Y 轴刻度出现 `402 / 201 / 0` 这类不整齐数字，改为 1/2/5×10ⁿ 取整后再出图。

最终验收结论：全部图表、结论卡、KPI、表格渲染正常。

## 五、产品设计上的几个判断

1. **只读白名单写进客户端**，而不是靠提示词约束。写操作（下单、领券、抽奖）在代码层直接拒绝，
   这是对用户账户最实在的保护，也是参赛作品应有的工程自觉。
2. **营养表是公共数据**，即使空号也能跑通一半链路——所以把它单独存成
   `assets/nutrition-table.txt`，既是演示数据的底料，也是离线兜底。
3. **结论卡按严重程度排序**（warn → info → good），打开页面第一眼看到的就是
   「沉睡积分」「钠超标」这种有行动欲的信息，而不是一张流水账。
4. **商品名匹配做四级兜底**（精确 → 去规格 → 包含 → 编辑距离+二元字组），
   应对「麦旋风奥利奥」↔「奥利奥麦旋风」这类倒装名；匹配不上的数量显式披露，不静默算错。

## 六、交付清单

| 大赛要求文件 | 状态 |
|---|---|
| `README.md` | ✅ |
| `CONTEST_DECLARATION.md` | ✅ 官方原文，字节级未改动（sha256 `cd28101b…`） |
| `MCP_INTEGRATION.md` | ✅ |
| `mcp-config.example.json` | ✅ 仅 `${MCD_MCP_TOKEN}` 占位符 |
| `workbuddy.md` | ✅ 本文件 |
| 源代码 | ✅ `scripts/` + `app/` |
