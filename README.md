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

## Run Demo

仓库内置了一条官方 demo：A 类文件业务 `A_DEMO`，输出科学绘图和报告。

样例数据见：

- [`examples/demo_a.csv`](/root/projects/pr_agents/examples/demo_a.csv)

完整演示步骤见：

- [`docs/demo.md`](/root/projects/pr_agents/docs/demo.md)

## WebUI Demo

现在默认用户入口是聊天式 Agent WebUI，而不只是 Swagger 或 `curl`。

- 打开 `http://<机器IP>:8000/`
- 左侧是会话列表和 `New chat`
- 右侧是聊天消息流，输入框固定在底部
- 点击 `Run A_DEMO`
- 页面会展示 Agent 计划、工具调用、任务结果和报告正文，但过程信息以次级执行卡片呈现
- 页面刷新后会优先恢复上一次活动会话
- 最近任务的结果快照会持久化到 SQLite，服务重启后仍可查询
- 顶部会显示当前 `Intent mode`：`fake` 或 `llm`

如果需要调试底层接口，再访问：

- `http://<机器IP>:8000/docs`

## Intent Mode

当前支持两种意图解析模式：

- `fake`
  默认模式。适合你在接真实业务 `Service` 时先稳定调通流程。
- `llm`
  使用 GLM 官方 API 的 provider 适配层解析自然语言；若失败会自动回退到 `fake`。

当前默认 LLM provider 为 `glm`，默认模型为 `GLM-4.5-Air`。为便于后续把代码拷贝到另一个局域网继续适配：

- API key 只从环境变量读取，不写进仓库
- provider HTTP 调用被封装在独立适配层里
- 后续若切换到别的模型或局域网代理，只需要替换配置或 provider 实现，不需要重写 Agent 主链路

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
