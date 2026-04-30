# API 说明

## Agent Session

- `POST /api/v1/agent/sessions`
  创建 Agent 会话。
- `GET /api/v1/agent/sessions/{session_id}`
  返回 messages、tasks、runs、sources。
- `POST /api/v1/agent/sessions/{session_id}/messages`
  创建新的 Agent run。
  请求体：
  - `content`
  - `source_id` 可选；分析请求推荐显式传入
  - `model_mode` 可选：`fake | llm`

## Session Source

- `POST /api/v1/agent/sessions/{session_id}/sources/csv-upload`
  multipart 上传 CSV。
  字段：
  - `file`
  - `business_code`，默认 `file_analysis`
- `POST /api/v1/agent/sessions/{session_id}/sources/database`
  注册 SQL 模拟 source。
  请求体：
  - `query_name`
  - `sql`
  - `business_code`，默认 `db_analysis`
  - `source_profile`
- `POST /api/v1/agent/sessions/{session_id}/sources/file`
  兼容接口，通过 JSON 文本内容注册 CSV source。
- `GET /api/v1/agent/sessions/{session_id}/sources`
  列出 source。
- `POST /api/v1/agent/sessions/{session_id}/demo-sources/{demo_code}`
  当前支持 `a_demo_file`、`a_demo_db`。

## Run Stream

- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
  通过 SSE 订阅运行事件。

主要事件：

- `run_started`
- `step_started`
- `tool_called`
- `task_queued`
- `task_status`
- `artifacts_ready`
- `tool_result`
- `step_completed`
- `step_failed`
- `assistant_started`
- `assistant_delta`
- `assistant_completed`
- `model_fallback`
- `run_completed`
- `run_failed`
- `session_snapshot`

## Task

- `GET /api/v1/tasks/{task_id}`
  查询任务详情、结果和 artifacts。
- `GET /api/v1/sessions/{session_id}/tasks`
  查询会话任务。
- `POST /api/v1/tasks/{task_id}/cancel`
  请求取消任务。

任务状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

## Artifact

- `GET /api/v1/artifacts/{artifact_id}`
  查询 artifact 元数据。
- `GET /api/v1/artifacts/{artifact_id}/content`
  读取文本 artifact。
- `GET /api/v1/artifacts/{artifact_id}/raw`
  读取原始 artifact，图表 SVG 使用该接口。

Artifact 类型：

- `table`
- `chart_image`
- `report`
- `dataset` 和 `chart` 为兼容类型。

## 兼容任务接口

- `POST /api/v1/tasks/file-analysis`
- `POST /api/v1/tasks/db-analysis`

这两个接口仍同步执行，主要用于回归测试和直接调试。Agent 工作台主流程使用 source + Agent run + SSE + 后台异步任务。
