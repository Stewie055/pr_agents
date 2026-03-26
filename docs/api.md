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
  返回聊天式 Agent WebUI

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

当前用户主入口是根路径 `/` 的聊天式 WebUI。

- 页面内可直接创建会话
- 可一键运行两条官方示例：
  - `Run File Demo`
  - `Run DB Demo`
- 会展示：
  - 用户消息
  - Agent 最终回复
  - 折叠的 `Task details`
- 页面刷新后会优先恢复最近活动 session
- 页面顶部会显示当前 `Intent mode`
- 普通聊天消息不会触发任务，也不会出现 tool_call
- 任务型消息会在 session 响应中返回 `runs`，其中包含计划状态和步骤摘要
- WebUI 不再等待整包消息执行完成，而是订阅 run 的 `SSE` 事件流
- WebUI 默认不把 `plan`、`tool_call`、`tool_result` 直接渲染成主消息
- 任务型 run 会聚合到 assistant 回复下方的折叠详情里；纯聊天 run 不会单独显示
- 页面内还提供两类标准追问：
  - `Show latest report`
  - `Summarize report`

## Intent Mode 配置

- `fake`
  规则式解析，适合开发和业务接入阶段
- `llm`
  基于 GLM 官方 API provider 的结构化意图解析；失败自动回退到 `fake`

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

普通聊天只会追加 `messages`；明确任务请求才会创建 `runs` 和 `tasks`。

当前官方 demo 推荐的两条 agent prompt：

- `Please use A_DEMO file data to generate a scientific plot and report.`
- `Please use database data to generate a scientific plot and report for A_DEMO.`

## SSE 事件

`GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream` 返回 `text/event-stream`，当前事件包括：

- `run_started`
- `chat_reply`
- `plan_created`
- `step_started`
- `tool_called`
- `tool_result`
- `step_completed`
- `step_failed`
- `run_completed`
- `run_failed`
- `session_snapshot`

第一版前端在收到事件后会刷新当前 session，以同步 `messages/tasks/runs` 的最新状态。
