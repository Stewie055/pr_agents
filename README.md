# pr_agents

`pr_agents` 是一个面向 Agent 的数据分析平台骨架，用于承接原 QT 数据可视化与分析工具的能力改造。

当前仓库实现的是可运行的第一版框架：

- 六层分层骨架：`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`
- 基于 Pydantic 的统一输入输出模型
- 基于 PydanticAI 的轻量 Agent/tool 封装
- 可替换的 `Service` 接口与 stub 实现
- 基于 `business_code` 的通用业务分派接口，覆盖 A/B 两类业务
- 文件分析、数据库分析、补生成报告三条主工作流
- FastAPI API 与 SQLite 任务/产物持久化
- 自动化测试覆盖接口契约、工具调用、工作流、编排与端到端闭环
- 基于 `React + Vite + TypeScript` 的诊断 Agent 工作台

## 快速开始

需要环境：

- `uv`
- Python 3.11+
- Node.js 20+
- `pnpm`

安装依赖：

```bash
uv sync --python 3.11
cd frontend && pnpm install
```

运行测试：

```bash
uv run pytest
cd frontend && pnpm test
```

启动 API：

```bash
uv run python -c "from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='0.0.0.0', port=8000)"
```

前端开发模式：

```bash
cd frontend && pnpm dev --host 0.0.0.0 --port 5173 --strictPort
```

## Run Demo

仓库内置两条官方 demo，默认都围绕 `A_DEMO` 展示科学绘图和报告：

- 文件主线：从原始文件入口触发分析
- 数据库主线：从清洗后数据库入口触发分析

样例数据见：

- [`examples/demo_a.csv`](/root/projects/pr_agents/examples/demo_a.csv)

完整演示步骤见：

- [`docs/demo.md`](/root/projects/pr_agents/docs/demo.md)

## WebUI

当前默认用户入口是独立 `React + Vite + TypeScript` 前端工作台。

- 根路径：`http://<机器IP>:8000/`
- 前端开发页：`http://<机器IP>:5173/`
- Swagger：`http://<机器IP>:8000/docs`
- 页面结构固定为：
  - 左侧 `Chat Panel`
  - 右侧 `Workbench`
  - 右侧 `Debug Drawer`
- 聊天区只保留对话和轻量工具状态
- 表格、图表、报告预览统一进入 `Workbench`
- 调试信息通过默认弱化的 `Debug Drawer` 承接

## Model Mode

当前支持两种模型模式：

- `fake`
  开发与业务适配模式。适合你在接真实业务 `Service` 时先稳定调通流程。
- `llm`
  对外 demo 推荐模式。使用 GLM 官方 API 的 provider 适配层驱动 Agent 决策；若失败会自动回退到 `fake`。

当前默认 LLM provider 为 `glm`，默认模型为 `GLM-4.5-Air`。为便于后续把代码拷贝到另一个局域网继续适配：

- API key 只从环境变量读取，不写进仓库
- provider HTTP 调用被封装在独立适配层里
- 后续若切换到别的模型或局域网代理，只需要替换配置或 provider 实现，不需要重写 Agent 主链路

## Agent Runtime

当前 Agent Orchestration 已收敛为单一 `AgentRuntime` 主入口，内部使用一个 `PydanticAI Agent` 作为执行主体。它不再先写死 `chat / report / task` 分支，而是：

- 通过 `ContextManager` 组装当前会话上下文
- 通过 `Memory` 提供短期和中期记忆
- 让模型自己决定是直接回复还是调用白名单 workflow-level tools
- 通过 deps 在工具之间传递最近报告、任务结果和产物引用
- 通过 SSE 持续推送运行事件，并把 run/step/message/task/artifact 持久化到 SQLite

当前模型由工厂在启动时注入：

- `FakeLLM`
  作为开发、回归测试和业务接入阶段的稳定模型
- `GLMProvider`
  作为真实模型 provider，当前默认模型为 `GLM-4.5-Air`

`PydanticAI` 被保留在 Agent 内部，负责模型承接、tool schema、工具调用和流式事件；领域业务仍然只在 `Workflow / Service`。

## Streaming

当前 WebUI 的消息发送链路是：

1. `POST /api/v1/agent/sessions/{session_id}/messages`
   创建一次新的 run
2. `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
   通过 `SSE` 接收：
   - `run_started`
   - `step_started`
   - `tool_called`
   - `tool_result`
   - `step_completed`
   - `step_failed`
   - `assistant_started`
   - `assistant_delta`
   - `assistant_completed`
   - `run_completed` / `run_failed`
   - `session_snapshot`

因此普通聊天会直接进入 assistant 文本流；任务型请求会先显示独立的工具/步骤卡片区，再在工具完成后继续输出 assistant 回复。

图表产物当前使用 stub 生成的 `SVG` 文件，前端通过 `raw artifact` 接口直接展示。

相关环境变量：

- `PR_AGENTS_INTENT_MODE`
- `PR_AGENTS_LLM_PROVIDER`
- `PR_AGENTS_LLM_BASE_URL`
- `PR_AGENTS_LLM_API_KEY`
- `PR_AGENTS_LLM_MODEL`
- `PR_AGENTS_LLM_TIMEOUT`

## 目录说明

```text
src/pr_agents/
  api/               FastAPI 路由
  application/       任务应用服务
  agent/             Agent Orchestration
  infrastructure/    文件与任务产物管理
  services/          业务能力接口与 stub 实现
  tools/             对 Agent 暴露的工具层
  webui/             WebUI 适配入口
  workflows/         可靠工作流编排
  models.py          统一数据模型
tests/               自动化测试
docs/                设计与说明文档
examples/            演示样例数据
```

## 当前默认实现

当前不包含 QT 真实业务代码。`Service` 层通过 `StubAnalysisPlatform` 提供可运行假实现，便于先跑通端到端链路；后续可由人工在 `services/` 中逐步替换为真实 QT 适配实现。

## 业务接口约定

当前所有分析入口都以 `business_code` 作为显式业务标识。

- A 类业务：
  每个业务有单独的数据文件，可通过 `source_profile.source_pattern=per_business_file` 表示
- B 类业务：
  多个业务共享同一数据文件，可通过 `source_profile.source_pattern=shared_file` 表示
- 文件和数据库入口都长期保留
- matplotlib 自定义科学绘图统一使用 `ChartArtifact` 返回，建议用 `chart_profile.chart_type=scientific_plot`

## 当前 API

- `POST /api/v1/tasks/file-analysis`
- `POST /api/v1/tasks/db-analysis`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/sessions/{session_id}/tasks`
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/raw`
- `GET /api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/raw`
