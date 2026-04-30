# pr_agents

`pr_agents` 是一个 Agent 驱动的数据分析工作台骨架，用于把原 QT 数据可视化与分析工具改造成可被自然语言调用、可追踪、可替换业务适配器的平台能力。

当前版本是第一阶段完整雏形：

- 产品形态：科研实验室风格的 React 数据分析工作台
- Agent：单一 PydanticAI `ReAct` Agent，默认 `fake` 模式，可配置 `llm`
- 数据源：真实 CSV 上传、SQL 表单注册、显式 demo source
- 执行：后台异步任务，支持 queued/running/succeeded/failed/cancelled
- 产物：结构化报告、图表图片 SVG、表格 artifact
- 持久化：SQLite 存 session/source/run/task/artifact 元数据，本地文件存上传和产物
- 业务：stub capability 模拟 QT 解析、清洗、分析、画图、报告生成

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
cd frontend && pnpm build
```

启动 API 和已构建前端：

```bash
uv run python main.py
```

前端开发模式：

```bash
cd frontend && pnpm dev --host 0.0.0.0 --port 5173 --strictPort
```

访问：

- 工作台：`http://127.0.0.1:8000/`
- 前端开发页：`http://127.0.0.1:5173/`
- Swagger：`http://127.0.0.1:8000/docs`

## 架构

实际依赖方向：

```text
WebUI
  -> REST API / SSE API
  -> Application Services
  -> Agent Runtime
  -> Agent Tools
  -> Use Cases / Task Service
  -> Business Capabilities / Stub Adapters
  -> Repositories / File Artifact Store
```

关键边界：

- `AgentRuntime` 只负责 ReAct loop、tool call、事件流和模型 fallback。
- Agent tool 是薄封装，主分析入口是 `analyze_source`。
- `TaskApplicationService` 负责任务创建、后台执行、取消、状态和产物持久化。
- `StubAnalysisPlatform` 模拟真实 QT 业务能力，后续可替换为真实 adapter。
- `ContextManager` 只使用显式选择的 source；未选择 source 时返回 clarification，不偷偷使用最新源。

## WebUI

前端不是普通聊天页，而是三栏工作台：

- 左侧：CSV 上传、SQL source 注册、source 选择、fake/LLM 模式切换、取消任务
- 中间：对话、prompt、Agent 工具步骤状态
- 右侧：run 概览、工具时间线、metrics/table、图表图片、报告预览

用户主流程：

1. 上传 CSV 或注册 SQL source。
2. 显式选择 source。
3. 输入“分析当前数据源，生成结构化报告和图表”。
4. 通过 SSE 查看 Agent tool、后台任务状态和 artifact 生成。
5. 在右侧查看报告、图表和表格结果。

## Model Mode

- `fake`：默认模式，确定性工具调用，适合测试和离线演示。
- `llm`：使用 OpenAI-compatible GLM provider；模型失败时同一 run 自动回退到 `fake`。

相关环境变量：

- `PR_AGENTS_INTENT_MODE`
- `PR_AGENTS_LLM_PROVIDER`
- `PR_AGENTS_LLM_BASE_URL`
- `PR_AGENTS_LLM_API_KEY`
- `PR_AGENTS_LLM_MODEL`
- `PR_AGENTS_LLM_TIMEOUT`

## 主要 API

- `POST /api/v1/agent/sessions`
- `POST /api/v1/agent/sessions/{session_id}/sources/csv-upload`
- `POST /api/v1/agent/sessions/{session_id}/sources/database`
- `GET /api/v1/agent/sessions/{session_id}/sources`
- `POST /api/v1/agent/sessions/{session_id}/messages`
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/raw`

兼容保留：

- `POST /api/v1/tasks/file-analysis`
- `POST /api/v1/tasks/db-analysis`
- `POST /api/v1/agent/sessions/{session_id}/demo-sources/{demo_code}`

## 目录说明

```text
src/pr_agents/
  api/               FastAPI 路由
  application/       会话、任务、执行应用服务
  agent/             ReAct Runtime、上下文、模型 provider
  infrastructure/    SQLite repository、本地 artifact store
  services/          QT 业务能力接口与 stub 实现
  tools/             workflow 工具注册
  workflows/         解析、清洗、分析、图表、报告流程
  models.py          统一 Pydantic 数据模型
frontend/            React + Vite 工作台
tests/               后端自动化测试
docs/                架构、API、演示和测试说明
```
