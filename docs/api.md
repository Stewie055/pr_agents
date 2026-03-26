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
  发送用户消息并触发 Agent
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
- 可一键运行 `A_DEMO`
- 会展示：
  - 用户消息
  - Agent 计划
  - 工具调用
  - 任务结果
  - 报告正文
- 页面刷新后会优先恢复最近活动 session
- 页面顶部会显示当前 `Intent mode`

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
