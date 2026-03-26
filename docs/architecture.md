# 架构说明

## 分层

依赖方向固定为：

`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`

### WebUI

负责用户输入、任务发起、结果展示、会话视图，不承载领域逻辑。当前通过 `FastAPI + 聊天式单页 WebUI` 作为用户入口，并通过 `SSE` 流式接收 Agent 运行事件。

### Agent Orchestration

负责根据用户意图选择 Tool 和组织参数，管理 session 和运行上下文。当前 Agent 运行时已拆为三段：

- `Conversation Router`
  快速区分普通聊天、报告追问和任务型请求
- `Planner`
  对任务型请求生成 workflow-level 结构化计划
- `Executor`
  按步骤执行 tool/workflow，记录观察结果并更新 run/step 状态
- `Event Stream`
  将 run 生命周期、步骤状态和关键 tool 结果通过 SSE 推给前端

### Tool

向 Agent 暴露粗粒度、业务友好的调用入口，负责参数校验和调用 Workflow。

### Workflow

负责把多个 Service 步骤可靠串联，维护产物传递、失败终止和结构化结果。

### Service

负责领域业务能力抽象，是人工接入 QT 能力的唯一入口。当前接口采用 `business_code` 驱动的通用模式，由具体实现决定业务属于 A 类还是 B 类。

### Infrastructure

负责任务目录、产物保存、文件引用和底层存储适配。当前已包含本地 artifact 落盘和 SQLite 元数据存储。

## 当前实现原则

- 所有接口统一使用 Pydantic 模型。
- Workflow 负责可靠流程，Service 负责领域能力。
- Tool 不直接耦合 QT 实现。
- 当前使用 stub 实现跑通闭环，后续替换为真实适配器。
- 任务执行采用同步模式，但统一使用 `task_id` 和状态机模型，便于后续扩展异步执行。
- A 类“单业务单文件”和 B 类“多业务共享文件”不拆成两套 API，只通过 `business_code` 和 `source_profile` 区分。
- 普通图表和 matplotlib 科学绘图统一建模为 `ChartArtifact`。
- 用户 Demo 路径采用聊天式 Agent 会话：用户消息 -> Agent 计划 -> Tool 调用 -> 任务结果 -> 报告内容。
- 官方 demo 当前包含两条主线：文件入口分析和数据库入口分析；两者共享同一套 Router / Planner / Executor / Workflow 链路。
- 当前 Agent 会话层已抽出独立意图解析器，并将任务结果快照持久化到 SQLite 以支持重启恢复。
- 当前意图解析器支持双模：
  - `fake`：规则式稳定模式
  - `llm`：通过 provider 适配层调用真实模型，当前默认 provider 为 `glm`，失败自动回退到 `fake`
- GLM 官方 API 的 HTTP 调用被隔离在独立 provider 中，`AgentSessionService` 和任务执行链路不直接依赖供应商细节。
- 默认模型配置为 `GLM-4.5-Air`，便于开发环境先验证自然语言理解；后续迁移到局域网环境时可只替换 provider 配置或实现。
- 普通聊天默认不触发工具；只有任务型请求才创建 plan/run/step 并执行 workflow。
- 第一版 Planner 粒度固定为 workflow-level，避免把领域逻辑推进 LLM。
- 前端发送消息时采用“POST 创建 run + GET SSE 订阅”模式，而不是等待整包 JSON 响应。
- WebUI 展示层采用“最终回复优先”的聚合策略：`plan/tool/run` 轨迹默认收敛到 assistant 回复下方的折叠详情，而不是分别平铺到消息流中。
