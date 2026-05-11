# ReAct Agent Loop

## Purpose

分析、诊断、报告请求使用 ReAct loop，而不是一次性工具规划。Agent 可以在看到工具 Observation 后继续选择下一步，直到形成最终结论。

## Flow

```text
Router -> State Gate -> reason -> act -> observe -> reason ... -> finalize
```

## Stop Conditions

- LLM 返回 final answer 且没有 tool calls。
- 达到 `max_steps=6`。
- 同一工具调用重复超过阈值。
- LLM 请求失败或返回未知工具。

## Observation Contract

工具 Observation 必须包含足够的结构化信息：

- `inspect_dataset`: columns、column_types、numeric_columns、row_count、preview。
- `profile_dataset`: per-column profile、evidence summary。
- `build_trend_chart`: chart type、series names、point count。
- `diagnose_performance`: possible causes、confidence、risk level、recommendations。
- `generate_report`: section headings and format。

Observation 不应包含完整原始文件内容。

## DeepSeek Compatibility

DeepSeek V4 thinking mode 会在 tool-call 轮次返回 `reasoning_content`。后续带 tool result 的请求必须把这段内容随 assistant tool-call message 原样传回。

## Prompt XML+JSON Tool Mode

未开启 auto-tool-choice 的模型部署使用 `SEMIDIAG_LLM_TOOL_MODE=prompt_xml_json`。该模式不发送 OpenAI `tools` 字段，而是用 XML 做协议边界、JSON 承载工具列表和参数：

- `<available_tools>`: 每轮由 ToolRegistry 动态生成工具清单。
- `<tool_calls>`: Runtime 解析块内 JSON 数组后执行白名单工具。
- `<observation>`: Runtime 将工具结果回灌给模型。
- `<final_answer>`: Runtime 停止 ReAct loop 并清洗最终回复。

Runtime 的工具执行、Observation、重复调用保护和 max step 策略与 native 模式一致。

XML+JSON 解析由独立 parser 负责。缺失动作块、同时出现 `<tool_calls>` 和 `<final_answer>`、多个 tool call 块、非法 JSON、空工具列表或非 object arguments 都会返回明确错误；首次格式错误会触发一次修复重试，并在 trace/audit 中保留可调试信息。

## Trace Debugging

每轮 ReAct 会写入 AgentStepTrace。Trace 调试台聚合：

- 路由和 stop reason。
- LLM audit request/response、provider、model、tool mode、耗时和错误。
- ToolCallTrace 和结构化 Observation。
- Artifact/Evidence 摘要。

Trace API 默认统一脱敏密钥和认证头，并截断超长文本。导出接口返回同样脱敏后的 JSON。

## User-Facing Output

最终回复会过滤内部 `case_`、`ds_`、`art_` 标识，并移除 DSML/tool-call 标记。前端主界面展示最终回复、工具摘要和 Artifact；独立调试台按需展示完整 step trace。
