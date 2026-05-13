# Service And Tool Contract

## Service Contract

Service 层放在 `business/services/`，不依赖 WebUI、Agent 或 LLM。它只接受结构化输入并返回结构化结果。

当前通用 CSV 分析 Service `business/services/csv_file_analysis.py` 提供：

- `parse_dataset`
- `profile_dataset`
- `build_chart`
- `diagnose`
- `generate_report`

真实业务迁移时，应优先把 Qt 程序里的解析、清洗、建模、绘图和报告逻辑抽成 Service。图表应由 Service 使用 Matplotlib 或业务绘图库生成 PNG/SVG/PDF 等文件，再通过 Artifact 暴露给 Agent 和 WebUI；Agent 不直接绘图。
Service 由 `business/plugins/*.py` 或 `business/tools/*.py` 调用。平台核心只关心 ToolDefinition、ToolResult、Artifact 和 Evidence。
解析类 Tool 会把 Service 提取出的结构化指标写入 `MetricRepository`；当前默认 SQLite 实现，生产目标是 ClickHouse adapter。
长耗时 Service 调用后续应由任务队列承载，Tool/API 负责创建任务和暴露状态，不让请求线程长期阻塞。
Workflow 重放复用 Tool Registry 执行步骤，因此 Tool 必须保持幂等或能安全重复生成新 Artifact/Trace。

## Tool Contract

每个 Tool 必须声明：

- `name`
- `description`
- `input_schema`
- `output_schema`
- `required_permissions`
- `risk_level`
- `origin`
- `phase`
- `capability_tags`
- `system_injected_args`

Tool 执行必须：

- 校验数据是否属于当前诊断案例。
- 调用 Service。
- 保存 Artifact/Evidence。
- 保存 ToolCallTrace。
- 写入 AuditEvent。

Tool 返回不能只有自然语言，必须产生结构化 `Artifact`、`Evidence` 或诊断 payload。

业务 Tool 可以来自两类来源：

- Common Tool：公共业务能力，来自 `business/tools/*.py`，启动时进入 common registry。
- Plugin Tool：测校项插件提供的工具，只有插件被选中后才进入本轮 active registry。

`dataset_id` 这类系统参数应放入 `system_injected_args`。Runtime 会自动注入，LLM 可见 schema 会隐藏这些字段，用户也不需要手动提供内部 ID。

## ToolResult Observation Payload

每个 ToolResult 必须提供给 Agent loop 使用的结构化 observation payload：

- `summary`
- `data`
- `artifact_ids`
- `evidence_ids`
- `next_suggestions`

Runtime 会补充 `tool_name` 并回填给 LLM。Observation 面向 LLM 推理，不等同于前端展示文本。它应包含足够的结构化信息，例如字段名、列类型、统计摘要、趋势序列名、诊断结论和建议动作，但不应包含完整原始文件内容。

通用 CSV 插件的 ToolResult.data 约定：

- `inspect_dataset`: columns、column types、numeric columns、row count、preview。
- `profile_dataset`: per-column profile、evidence summary。
- `build_trend_chart`: render type、chart count、chart title、figure kind、display group、series names、point count。
- `diagnose_performance`: possible causes、confidence、risk level、recommendations。
- `generate_report`: section headings、format、MIME type、chart count、template engine。

业务插件可定义自己的 `data` schema，但必须写在 ToolDefinition.output_schema 和插件开发文档中，保证 LLM、Trace 调试台和前端可以理解。

## Artifact Types

当前支持：

- `dataset`
- `table`
- `chart`
- `model_result`
- `diagnosis`
- `report`
- `file`

## File Artifacts

图表和报告类 Artifact 应在 `data` 中提供：

- `render_type`: 例如 `image`。
- `format` 或 `mime_type`。
- `filename`。
- `file_url`: 例如 `/api/artifacts/{artifact_id}/file`。
- `figure_kind`、`display_group`、`order`: 用于前端多图分组、排序和切换。

`file_path` 只服务于后端文件读取，不应在用户界面展示。

## Report Generation

PPTX 报告优先使用 `ppt-template-sdk`。模板 shape 命名遵循 `ph:<type>:<key>`，例如 `ph:text:title`、`ph:image:primary_chart`。当前示例会在生成目录创建默认模板并渲染 PPTX；真实业务插件应替换为正式模板和 renderer。
