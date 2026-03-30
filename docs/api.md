# API 说明

## 核心接口

- `POST /api/v1/tasks/file-analysis`
  同步执行文件分析任务
- `POST /api/v1/tasks/db-analysis`
  同步执行数据库分析任务
- `GET /api/v1/tasks/{task_id}`
  查询任务详情、结果摘要和 artifact 列表
- `GET /api/v1/sessions/{session_id}/tasks`
  查询会话下的任务列表
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/content`
- `GET /api/v1/artifacts/{artifact_id}/raw`

## Agent Session

- `POST /api/v1/agent/sessions`
  创建 Agent 会话
- `GET /api/v1/agent/sessions/{session_id}`
  返回：
  - `messages`
  - `tasks`
  - `runs`
  - `sources`
- `POST /api/v1/agent/sessions/{session_id}/messages`
  创建新的 Agent run，请求体：
  - `content`
  - `source_id` 可选；不传时默认取最近 source
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
  通过 SSE 订阅运行事件

## Session Source

Agent 的分析类请求依赖显式 source。

- `POST /api/v1/agent/sessions/{session_id}/sources/file`
  请求体：
  - `file_name`
  - `content`
  - `source_profile`
- `POST /api/v1/agent/sessions/{session_id}/sources/database`
  请求体：
  - `query_name`
  - `sql`
  - `source_profile`
- `GET /api/v1/agent/sessions/{session_id}/sources`
  返回当前会话下所有 source
- `POST /api/v1/agent/sessions/{session_id}/demo-sources/{demo_code}`
  当前支持：
  - `a_demo_file`
  - `a_demo_db`

## SSE 事件

当前事件包括：

- `run_started`
- `tool_called`
- `tool_result`
- `step_started`
- `step_completed`
- `step_failed`
- `assistant_started`
- `assistant_delta`
- `assistant_completed`
- `model_fallback`
- `run_completed`
- `run_failed`
- `session_snapshot`

## 第一阶段约束

- 使用 JSON 请求，不支持 multipart 上传
- 文件 source 当前仍使用文本内容注册
- database source 当前仍使用 `query_name + sql` stub，不接真实数据库连接池
- 同步执行模型，不包含鉴权、限流和异步队列
- `llm` 只对模型调用失败做 fallback，不对业务工具失败做 fallback
