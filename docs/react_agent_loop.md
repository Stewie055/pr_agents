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

## User-Facing Output

最终回复会过滤内部 `case_`、`ds_`、`art_` 标识，并移除 DSML/tool-call 标记。前端展示最终回复、工具轨迹和 Artifact；完整 step trace 先保存在后端。
