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

当前 `AgentRuntime` 使用 deterministic `StubLLMProvider`，根据消息内容选择工具序列：

- 数据解析。
- 指标画像。
- 趋势图数据生成。
- 初步性能诊断。
- 报告草稿生成。

后续可替换为内网 OpenAI-compatible LLM provider。替换时应保留工具白名单、权限检查和审计记录。

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
