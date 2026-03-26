# pr_agents

`pr_agents` 是一个面向 Agent 的数据分析平台骨架，用于承接原 QT 数据可视化与分析工具的能力改造。

当前仓库实现的是可运行的第一版框架：

- 六层分层骨架：`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`
- 基于 Pydantic 的统一输入输出模型
- 基于 PydanticAI 的最小 Agent/tool 封装
- 可替换的 `Service` 接口与 stub 实现
- 基于 `business_code` 的通用业务分派接口，覆盖 A/B 两类业务
- 文件分析、数据库分析、补生成报告三条主工作流
- FastAPI API 与 SQLite 任务/产物持久化
- 自动化测试覆盖接口契约、工具调用、工作流、编排与端到端闭环

## 快速开始

需要环境：

- `uv`
- Python 3.11+

安装依赖：

```bash
uv sync --python 3.11
```

运行测试：

```bash
uv run pytest
```

启动 API：

```bash
uv run python -c "from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='127.0.0.1', port=8000)"
```

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
