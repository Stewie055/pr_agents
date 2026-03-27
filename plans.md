# plans

## 已完成的第一阶段

- 建立 Python 项目骨架和依赖声明。
- 定义统一 Pydantic 数据模型与错误模型。
- 建立 `Service` 接口和 stub 实现。
- 建立三条主工作流：
  - 文件分析
  - 数据库分析
  - 基于已有产物生成报告
- 建立 Tool 层与最小 PydanticAI Agent 封装。
- 建立 WebUI 门面接口。
- 建立自动化测试与文档。

## 已完成的第二阶段

- 增加 FastAPI API 入口。
- 增加 SQLite 持久化仓储，保存 session、task、artifact 元数据。
- 增加任务应用服务和同步执行状态流转。
- 增加 API、持久化、失败场景测试。

## 已完成的第三阶段

- 在文件和数据库分析入口中引入 `business_code` 统一业务标识。
- 为通用接口补充 `source_profile`、`clean_profile`、`analysis_profile`、`chart_profile`、`report_profile`。
- 用 stub 实现 A 类单业务单文件和 B 类共享文件两种分派示例。
- 将 matplotlib 科学绘图统一收敛到 `ChartArtifact`，通过 `chart_type=scientific_plot` 区分。
- 增加共享文件和科学绘图场景的自动化测试。

## 已完成的第四阶段

- 补充官方 `A_DEMO` HTTP API demo 路径。
- 新增 demo 样例数据和独立演示文档。
- 在 README 中增加 Run Demo 入口。
- 增加官方 demo 闭环回归测试。

## 第五阶段计划与实现

- 增加聊天式 Agent 会话服务，而不是仅提供表单/API demo。
- 增加 Agent session API：创建会话、发送消息、读取会话状态和报告内容。
- 在 FastAPI 根路径提供单页 WebUI，展示 Agent 计划、工具调用和结果。
- 支持官方 `A_DEMO` 快捷按钮和多轮追问“重新查看报告”。
- 增加会话消息持久化与 WebUI/Agent 会话测试。

## 第六阶段计划与实现

- 将 WebUI 从“调试型 demo 面板”重做为对话优先的聊天布局。
- 增加左侧会话列表、`New chat` 入口和当前会话标题。
- 将输入区固定在主区底部，并支持 Enter 发送、Shift+Enter 换行。
- 将计划和工具调用降级为可展开的执行卡片，而不是主消息流中的大块文本。
- 保留 `Run A_DEMO` 快捷入口，但使其融入聊天交互。

## 第七阶段计划与实现

- 将 `WorkflowResult` 快照持久化到 SQLite，支持服务重启后的任务结果恢复。
- 为 Agent 新增独立的自然语言意图解析层，而不是把判断逻辑散落在 session service 中。
- 让 WebUI 页面优先恢复上一次活动会话，而不是每次刷新都新建 session。
- 补充任务结果恢复和意图解析的自动化测试。

## 第八阶段计划与实现

- 将模型层升级为 fake / llm 双模可切换架构。
- 保留 `FakeLLM`，作为业务 `Service` 适配阶段的默认稳定模式。
- 接入真实 llm provider，并在失败时自动回退到 fake。
- 增加 `PR_AGENTS_INTENT_MODE`、LLM base URL、API key、model、timeout 配置。
- 在 WebUI 和 Agent metadata 中展示当前模式与是否发生 fallback。

## 第九阶段计划与实现

- 将 llm 调用收敛为 provider 抽象，不再把 HTTP 调用直接写在 parser 里。
- 新增 `GLMProvider`，用于承接 GLM 官方 API。
- 保持 `fake` 与 `llm` 双模共存，默认仍使用 `fake` 以便先适配业务 `Service`。
- 新增 `PR_AGENTS_LLM_PROVIDER` 配置，默认 provider 为 `glm`，默认模型为 `GLM-4.5-Air`。
- LLM API key 只允许通过环境变量注入，不进入仓库。
- 在模型层保留 fallback，provider 未配置、超时、响应非法时自动退回 `fake`。
- 继续保持 Agent 会话层、任务层和 Workflow 层不直接依赖供应商实现，方便后续迁移到局域网环境。

## 第十阶段计划与实现

- 将 Agent 从“意图解析后直接调 workflow”升级为真正的任务型运行时。
- 引入单一 `AgentRuntime` 主入口，内部使用 `ContextManager`、`Memory` 和一个 `PydanticAI Agent` 统一承接决策与工具调用。
- 不再由 runtime 预先写死 `chat / report / task` 分支，而是让模型自行决定直接回复还是调用工具。
- 工具粒度固定为 workflow-level，步骤轨迹持久化到 SQLite。
- 对任务型请求返回 `runs`，包含 run 状态、步骤状态和关键 observation 摘要。
- WebUI 改为普通聊天只显示消息，任务请求额外显示折叠的 `Task details`。

## 第十一阶段计划与实现

- 将 Agent 消息发送改造成 `POST 创建 run + GET SSE 订阅` 的流式模式。
- 新增 run 级 SSE 事件：`run_started`、`step_started`、`tool_called`、`tool_result`、`step_completed`、`assistant_started`、`assistant_delta`、`assistant_completed`、`run_completed`、`run_failed`、`session_snapshot`。
- WebUI 发送消息后改用 `EventSource` 订阅事件，不再等待整包 JSON 才更新界面。
- 继续以 SQLite 作为最终状态来源，SSE 只负责实时观察；前端只在 run 结束时再对齐 session 快照。
- 保留现有 `GET session`、task、artifact 查询接口作为恢复和回放入口。

## 第十二阶段计划与实现

- 收敛 Agent 默认输出层级，主消息区只保留用户输入和 assistant 最终回复。
- 不再把 `plan`、`tool_call`、`tool_result` 作为独立主消息渲染。
- 将任务 run 轨迹聚合到 assistant 回复下方的折叠 `Task details` 中，避免与主回复重复。
- 将任务型最终回复从“摘要+完整报告正文”改成仅返回摘要，并把原始报告文本放入 `report_preview` 供折叠详情展示。
- 保持 SQLite 中的消息、run、step 原始数据不删减，只改变 WebUI 默认展示方式。

## 第十三阶段计划与实现

- 将官方 demo 从单一 `A_DEMO` 文件链路升级为双主线示例：
  - 文件分析主线
  - 数据库分析主线
- WebUI 新增 `Run File Demo`、`Run DB Demo` 和报告摘要追问快捷入口。
- 报告追问扩展为两类：
  - 返回完整报告
  - 返回报告重点摘要
- README 与 `docs/demo.md` 改写为面向外部展示的示例手册，默认以 `llm` 模式演示，`fake` 作为开发回退说明。

## 第十四阶段计划与实现

- 将 Agent Orchestration 重构为以 `AgentRuntime` 为中心的架构，不再保留旧的 intent parser 主链路。
- 新增 `FakeLLM`、`GLMProvider`、`ContextManager`、`MemoryManager`，并把执行收敛到单个 `PydanticAI Agent` 主链路。
- 通过工厂在启动时注入不同 llm，实现 fake / llm 切换，而不是在上层 runtime 中散布分支。
- `Memory` 作为正式一层，当前实现短期与中期记忆；长期知识和 RAG 作为后续扩展位，归属于 Memory，而不是单独平级模块。
- 运行时只允许调用 workflow-level tools，不直接把 Service 级能力暴露给模型。
- 删除旧的 `agent/intents.py`，避免旧的 parser 架构继续干扰后续业务接入。

## 第十五阶段计划与实现

- 将 WebUI 从“事件到达后整包刷新 session”改成真正的增量渲染。
- 后端新增 `assistant_started`、`assistant_delta`、`assistant_completed` 事件，用于流式输出最终回复。
- 工具型请求保持先显示 `step / tool` 卡片，再在工具完成后流式输出 assistant 回复。
- 直接回复路径也改成 assistant 文本流，而不是等待整段内容一次性落盘后再显示。
- 前端只在 run 完成后再对齐最终 session 快照，避免工具卡闪烁和重复渲染。
- 实时工具流不再依赖 assistant 气泡承接，而是使用独立工具区展示，避免页面只剩 `Thinking...`。

## 第十六阶段计划与实现

- 将 WebUI 从 FastAPI 内嵌 HTML 重构为独立的 `Vue + Vite` SPA。
- 保留后端 `FastAPI + SSE + PydanticAI Agent` 主链路，不引入 WebSocket。
- 前端正式区分三类状态：
  - 已持久化消息
  - 运行中的工具区
  - 运行中的 assistant 文本
- 根路径 `/` 在构建后直接返回 `frontend/dist/index.html`，静态资源由 FastAPI 托管。
- 引入可选的 Playwright 浏览器级回归测试，在具备浏览器环境时显式验证：
  - 普通聊天正文长度逐步增长
  - 工具型请求先出现 `Task in progress`
  - 工具完成后 assistant 文本继续增长
- 构建链改为 `pnpm`，前端锁文件改为 `pnpm-lock.yaml`。

## 第十七阶段计划与实现

- 将前端从“聊天页 + 少量运行卡片”重构为诊断工作台：
  - 左侧 `Chat Panel`
  - 中间 `Workbench`
  - 右侧 `Debug Drawer`
  - 底部 `Global Status Bar`
- 前端状态层升级为工作台视图模型，统一映射：
  - `workspaceState`
  - `processState`
  - `artifactState`
  - `debugState`
  - `statusBarState`
- 拆出组件树与 composable：
  - `useAgentWorkspace`
  - `useDebugDrawerState`
  - `components/chat/*`
  - `components/workbench/*`
  - `components/debug/*`
  - `components/layout/*`
- `Debug Drawer` 整体可折叠，内部模块也支持单独折叠。
- `Execution Controls` 当前通过 mock 交互提供 `Pause / Resume / Rerun Step / Modify State`，为后续真实 agent 控制接口预留挂接点。
- 可选浏览器级回归扩展到页面状态和工作台交互，而不只验证文本流。

## 下一阶段建议

- 增加真实 QT Service 适配器。
- 增加跨服务重启的完整会话列表恢复与排序策略。
- 增加异步任务执行。
- 增加长期知识库与 RAG 读取。
- 让 `Memory` 从当前短期/中期扩展到长期知识能力。
