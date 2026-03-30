# pr_agents

`pr_agents` 是一个面向 Agent 的数据分析平台骨架，用于承接原 QT 数据可视化与分析工具的能力改造。

当前版本已经收敛到第一阶段的 `ReAct` 单 Agent 模式：

- 六层分层：`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`
- 单一 `AgentRuntime` 作为 Agent 主入口
- React 工作台作为正式用户入口
- 会话级 source 注册，替代 runtime 内置 demo 输入
- `fake / llm` 双模与运行时 fallback
- FastAPI + SQLite 持久化任务、运行轨迹、source 和产物
- stub `Service` 保证在无 QT 源码时可跑通闭环

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

启动 API：

```bash
uv run python main.py
```

前端开发模式：

```bash
cd frontend && pnpm dev --host 0.0.0.0 --port 5173 --strictPort
```

## Agent Runtime

当前 Agent 层采用单一 `ReAct` loop：

- `ContextManager` 负责拼装会话上下文、最近任务、最近报告和可用 source
- `MemoryManager` 当前提供短期和中期记忆
- 模型只允许调用白名单 workflow-level tools
- Agent 工具只通过 `TaskApplicationService` 发起任务
- 模型失败时，`llm` 模式会在同一 run 内回退到 `fake`

当前白名单工具：

- `run_file_analysis_workflow`
- `run_db_analysis_workflow`
- `load_latest_report`
- `summarize_report`

## Session Source

分析类消息不再隐式读取 `examples/demo_a.csv` 或固定 SQL。当前 Agent 使用会话级 source：

- `file source`
  通过 `file_name + content + source_profile` 注册
- `database source`
  通过 `query_name + sql + source_profile` 注册
- `demo source`
  通过显式 helper API 注册 `a_demo_file / a_demo_db`

如果当前会话没有匹配的 source，Agent 会直接提示用户先注册 source，而不是偷偷跑 demo。

## WebUI

当前默认用户入口是独立 `React + Vite + TypeScript` 前端工作台。

- 根路径：`http://<机器IP>:8000/`
- 前端开发页：`http://<机器IP>:5173/`
- Swagger：`http://<机器IP>:8000/docs`
- 页面结构固定为：
  - 左侧 `Chat Panel`
  - 右侧 `Workbench`
  - 右侧 `Debug Drawer`

Quick Prompts 当前会先注册 demo source，再发送 prompt。

## Model Mode

- `fake`
  开发与业务适配模式，默认稳定回归模式
- `llm`
  使用 GLM 官方 API provider 驱动 Agent 决策；若模型调用失败，会回退到 `fake`

相关环境变量：

- `PR_AGENTS_INTENT_MODE`
- `PR_AGENTS_LLM_PROVIDER`
- `PR_AGENTS_LLM_BASE_URL`
- `PR_AGENTS_LLM_API_KEY`
- `PR_AGENTS_LLM_MODEL`
- `PR_AGENTS_LLM_TIMEOUT`

## Demo

仓库内置两条官方 demo，默认都围绕 `A_DEMO` 展示科学绘图和报告：

- 文件主线：显式注册 `a_demo_file` source 后触发分析
- 数据库主线：显式注册 `a_demo_db` source 后触发分析

样例数据见：

- [`examples/demo_a.csv`](/root/projects/pr_agents/examples/demo_a.csv)

完整演示步骤见：

- [`docs/demo.md`](/root/projects/pr_agents/docs/demo.md)

## 目录说明

```text
src/pr_agents/
  api/               FastAPI 路由
  application/       应用服务与执行服务
  agent/             Agent Orchestration
  infrastructure/    SQLite、artifact、session source 持久化
  services/          业务能力接口与 stub 实现
  tools/             对 Agent 暴露的工具层
  workflows/         可靠工作流编排
  models.py          统一数据模型
tests/               自动化测试
docs/                设计与说明文档
examples/            演示样例数据
```

## 当前 API

- `POST /api/v1/tasks/file-analysis`
- `POST /api/v1/tasks/db-analysis`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/sessions/{session_id}/tasks`
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/raw`
- `POST /api/v1/agent/sessions`
- `GET /api/v1/agent/sessions/{session_id}`
- `POST /api/v1/agent/sessions/{session_id}/messages`
- `POST /api/v1/agent/sessions/{session_id}/sources/file`
- `POST /api/v1/agent/sessions/{session_id}/sources/database`
- `GET /api/v1/agent/sessions/{session_id}/sources`
- `POST /api/v1/agent/sessions/{session_id}/demo-sources/{demo_code}`
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
