# API 说明

## 接口

- `POST /api/v1/tasks/file-analysis`
  同步执行文件分析任务，返回 `task_id`、`session_id`、`status` 和 `result`
- `POST /api/v1/tasks/db-analysis`
  同步执行数据库分析任务
- `GET /api/v1/tasks/{task_id}`
  查询任务详情、结果摘要和 artifact 列表
- `GET /api/v1/sessions/{session_id}/tasks`
  查询同一会话下的任务列表
- `GET /api/v1/artifacts/{artifact_id}`
  查询 artifact 元数据
- `GET /api/v1/artifacts/{artifact_id}/content`
  读取文本类产物内容
- `POST /api/v1/agent/sessions`
  创建 Agent 聊天会话
- `GET /api/v1/agent/sessions/{session_id}`
  查询 Agent 会话消息和关联任务
- `POST /api/v1/agent/sessions/{session_id}/messages`
  创建一次新的 Agent run，返回 `run_id` 和 `stream_url`
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
  通过 `SSE` 流式读取 Agent 事件
- `GET /api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/content`
  读取当前会话内的报告内容
- `GET /`
  返回构建后的 Vue 聊天式 Agent WebUI

## 第一版约束

- 使用 JSON 请求，不支持 multipart 上传
- 使用同步执行模型
- 只支持文本类 artifact 内联读取
- 不包含鉴权、限流和异步队列

## 业务参数约定

文件和数据库分析请求都应携带：

- `business_code`
  显式业务标识，例如 `A001`、`B015`
- `source_profile`
  来源补充参数。文件入口可用 `source_pattern=per_business_file` 或 `source_pattern=shared_file`
- `clean_profile`
  业务清洗参数透传
- `analysis_profile`
  业务分析参数透传
- `chart_profile`
  图表参数透传。科学绘图建议使用 `chart_type=scientific_plot`
- `report_profile`
  报告参数透传

当前 API 层只做参数承接和透传，不解释业务规则。

## Agent Demo

当前用户主入口是根路径 `/` 的 Vue 诊断工作台。

- 页面由独立 `Vue + Vite` SPA 实现，FastAPI 负责托管构建产物
- 页面结构：
  - Chat Panel
  - Workbench
  - Debug Drawer
  - Global Status Bar
- `Workbench` 会同时展示：
  - 流程图
  - 当前步骤
  - 任务日志
  - 图表、摘要、建议、报告预览等工件
- `Debug Drawer` 默认收起，并包含：
  - Tool Calls
  - Prompt Snapshot
  - Memory State
  - Execution Controls
- `Execution Controls` 当前为 mock 控件，后续接真实暂停/恢复接口时可直接替换

## Model Mode 配置

- `fake`
  规则式模型，适合开发和业务接入阶段
- `llm`
  基于 GLM 官方 API provider 的 `PydanticAI Agent` 决策；失败自动回退到 `fake`

当前默认 LLM 配置约定：

- `provider = glm`
- `model = GLM-4.5-Air`
- API key 只从环境变量读取
- 若未来迁移到局域网环境，可通过替换 provider 配置或 provider 实现继续复用当前 Agent 主链路

环境变量：

- `PR_AGENTS_INTENT_MODE`
- `PR_AGENTS_LLM_PROVIDER`
- `PR_AGENTS_LLM_BASE_URL`
- `PR_AGENTS_LLM_API_KEY`
- `PR_AGENTS_LLM_MODEL`
- `PR_AGENTS_LLM_TIMEOUT`

## Agent Session 响应

`GET /api/v1/agent/sessions/{session_id}` 现在返回：

- `messages`
  聊天消息和执行摘要消息
- `tasks`
  workflow 级任务记录
- `runs`
  Agent 运行轨迹。每个 run 包含：
  - `goal`
  - `status`
  - `summary`
  - `steps`

普通聊天只会追加 `messages`；任务型请求才会创建 `runs` 和 `tasks`。这些行为由单一 `PydanticAI Agent` 的决策驱动，而不是 API 层的硬编码分流。

当前官方 demo 推荐的两条 agent prompt：

- `Please use A_DEMO file data to generate a scientific plot and report.`
- `Please use database data to generate a scientific plot and report for A_DEMO.`

## SSE 事件

`GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream` 返回 `text/event-stream`，当前事件包括：

- `run_started`
- `step_started`
- `tool_called`
- `tool_result`
- `step_completed`
- `step_failed`
- `assistant_started`
- `assistant_delta`
- `assistant_completed`
- `run_completed`
- `run_failed`
- `session_snapshot`

当前前端会直接消费这些事件：

- 工具型请求先用 `step_started / tool_called / tool_result` 增量更新独立工具卡片区
- assistant 回复通过 `assistant_started / assistant_delta / assistant_completed` 增量渲染
- 最后再用 `run_completed / session_snapshot` 对齐持久化状态

前端开发与测试命令：

```bash
cd frontend
pnpm install
pnpm build
```

如果本地环境具备浏览器运行条件，可选执行：

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:browser:optional
```
