# Agent Design

## Role

Agent 是辅助诊断编排者，不是最终诊断责任主体。它负责：

- 理解工程师问题。
- 选择白名单工具。
- 汇总工具输出。
- 组织证据链。
- 生成辅助诊断建议和报告草稿。

正式结论和处置建议需要授权工程师确认。

## Runtime

`AgentRuntime` 支持两种 LLM provider：

- `StubLLMProvider`：未配置真实 LLM 时的离线模式，根据消息内容选择固定工具序列。
- `OpenAICompatibleProvider`：调用 OpenAI-compatible `/v1/chat/completions`，使用 tool calling 选择工具。

Stub 模式根据消息内容选择工具序列：

- 数据解析。
- 指标画像。
- 趋势图数据生成。
- 初步性能诊断。
- 报告草稿生成。

真实 LLM 模式执行 ReAct/Graph 流程：

1. LLM Router/Triage 先输出结构化 `RouteDecision`。
2. State Gate 检查当前状态是否满足该路径，例如分析/诊断/报告是否已有数据集。
3. 需要工具时进入 ReAct loop，让模型返回 tool calls。
4. 执行白名单工具，将结构化 Observation 回填给模型。
5. 模型可以继续调用工具或输出 final answer，直到 final、重复调用保护或 `max_steps`。

模型失败、超时、非法 tool call 或未知工具时，API 返回错误，不自动降级 stub。只有未配置真实 LLM 时才使用 stub。

## Router And State Gate

Router 由 LLM 完成，不使用规则分类器代替语义判断。`RouteDecision` 包含：

- `intent`: chat_response / knowledge_qa / data_analysis / diagnosis / report_generation / workflow_request / clarification
- `requires_dataset`
- `requires_knowledge`
- `target_workflow`
- `user_goal`
- `response_style`
- `reason`

本地 State Gate 不判断用户语义，只做确定性检查：

- 分析、诊断、报告需要数据但当前没有上传文件时，直接提示上传 CSV。
- 系统自动使用当前案例最新上传的数据集。
- 用户不需要也不应该手动提供 dataset id。

用户可见回复会过滤内部 `case_`、`ds_`、`art_` 等标识。

## ReAct Loop

分析、诊断、报告路径使用轻量状态机：

- `reason`: LLM 基于当前上下文和 observations 选择下一步。
- `act`: 执行一个或多个白名单工具。
- `observe`: 将工具结果转成结构化 Observation 回填模型。
- `finalize`: 模型输出最终面向用户的回复。

默认 `max_steps=6`。重复调用同一工具超过阈值时停止，避免死循环。工具执行错误不会直接终止请求，而是作为 error observation 回填给模型。

当前 CSV 示例工具包括：

- `inspect_dataset`: 查看字段、列类型、行数和样例。
- `parse_dataset`: 解析并建立数据集 artifact。
- `profile_dataset`: 统计画像并生成 evidence。
- `build_trend_chart`: 生成趋势图数据。
- `diagnose_performance`: 基于 evidence 生成辅助诊断。
- `generate_report`: 生成可编辑报告草稿。

## LLM Context

发送给模型的上下文只包含：

- DiagnosticCase 摘要。
- 数据集 id、文件名和 content type。
- Artifact id、类型、标题、摘要。
- Evidence id、类型、标题、摘要。
- 最近用户和助手消息。
- 中期记忆摘要。

原始设备文件内容和行级 CSV 数据不直接发送给 LLM。

## Audit

LLM 调用会记录：

- provider 和 model。
- messages 和 tools。
- tool calls / response。
- 错误和耗时。

API key 和 Authorization header 不能进入审计记录。

## Memory

当前实现：

- 短期记忆：诊断案例消息历史。
- 中期记忆：内存摘要接口。
- 长期记忆：关键词检索桩。

长期目标是将中长期记忆持久化，并接入可替换 RAG 存储。

## Human In The Loop

高风险动作必须进入审批：

- 代码执行。
- 数据写入。
- Workflow 发布。
- 正式报告发布。
- 处置建议确认。

当前 Tool Registry 已包含 `risk_level` 字段和高风险工具拦截逻辑。
