# 架构说明

## 分层

依赖方向固定为：

`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`

### WebUI

负责用户输入、任务发起、结果展示、会话视图，不承载领域逻辑。当前通过 `FastAPI + WebUIFacade` 作为后端入口。

### Agent Orchestration

负责根据用户意图选择 Tool 和组织参数，管理 session 和运行上下文。

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
