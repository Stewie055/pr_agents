# Service And Tool Contract

## Service Contract

Service 层不依赖 WebUI、Agent 或 LLM。它只接受结构化输入并返回结构化结果。

当前示例 `CSVDiagnosticService` 提供：

- `parse_dataset`
- `profile_dataset`
- `build_chart`
- `diagnose`
- `generate_report`

真实业务迁移时，应优先把 Qt 程序里的解析、清洗、建模、绘图和报告逻辑抽成 Service。

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

## Artifact Types

当前支持：

- `dataset`
- `table`
- `chart`
- `model_result`
- `diagnosis`
- `report`
- `file`
