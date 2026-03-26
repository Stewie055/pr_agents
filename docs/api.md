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
