# Service And Tool Contract

## Service Contract

Service 层不依赖 WebUI、Agent 或 LLM。它只接受结构化输入并返回结构化结果。

当前示例 `CSVDiagnosticService` 提供：

- `parse_dataset`
- `profile_dataset`
- `build_chart`
- `diagnose`
- `generate_report`

真实业务迁移时，应优先把 Qt 程序里的解析、清洗、建模、绘图和报告逻辑抽成 Service。图表应由 Service 使用 Matplotlib 或业务绘图库生成 PNG/SVG/PDF 等文件，再通过 Artifact 暴露给 Agent 和 WebUI；Agent 不直接绘图。
Runtime 通过 `PluginRegistry` 按案例 `equipment_type` 选择 Service 所在插件，因此真实业务迁移应新增插件并注册，不应让 Agent 直接判断业务类型。

## Tool Contract

每个 Tool 必须声明：

- `name`
- `description`
- `input_schema`
- `output_schema`
- `required_permissions`
- `risk_level`

Tool 执行必须：

- 校验数据是否属于当前诊断案例。
- 调用 Service。
- 保存 Artifact/Evidence。
- 保存 ToolCallTrace。
- 写入 AuditEvent。

Tool 返回不能只有自然语言，必须产生结构化 `Artifact`、`Evidence` 或诊断 payload。

## Tool Observation

每个 ToolResult 必须提供给 Agent loop 使用的结构化 Observation：

- `tool_name`
- `summary`
- `data`
- `artifact_ids`
- `evidence_ids`
- `next_suggestions`

Observation 面向 LLM 推理，不等同于前端展示文本。它应包含足够的结构化信息，例如字段名、列类型、统计摘要、趋势序列名、诊断结论和建议动作，但不应包含完整原始文件内容。

当前工具 Observation 约定：

- `inspect_dataset`: columns、column types、numeric columns、row count、preview。
- `profile_dataset`: per-column profile、evidence summary。
- `build_trend_chart`: render type、chart count、chart title、figure kind、display group、series names、point count。
- `diagnose_performance`: possible causes、confidence、risk level、recommendations。
- `generate_report`: section headings、format、MIME type、chart count、template engine。

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
