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

真实 LLM 模式执行两阶段流程：

1. 发送 system prompt、案例上下文摘要、最近消息和 tools schema，让模型返回 tool calls。
2. 执行白名单工具，将工具结果摘要回填给模型，生成最终中文回答。

模型失败、超时、非法 tool call 或未知工具时，API 返回错误，不自动降级 stub。只有未配置真实 LLM 时才使用 stub。

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
