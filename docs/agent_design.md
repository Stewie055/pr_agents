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
- `OpenAINativeToolProvider`：调用 OpenAI-compatible `/v1/chat/completions`，使用原生 `tools/tool_choice`。
- `OpenAIPromptXmlJsonProvider`：调用同一接口，但不发送 `tools/tool_choice`，使用 XML+JSON 文本工具协议。

Stub 模式根据消息内容选择工具序列：

- 数据解析。
- 指标画像。
- 趋势图数据生成。
- 初步性能诊断。
- 报告草稿生成。

真实 LLM 模式执行 ReAct/Graph 流程：

1. LLM Router/Triage 先输出结构化 `RouteDecision`。
2. State Gate 检查当前状态是否满足该路径，例如分析/诊断/报告是否已有数据集。
3. 需要工具时进入 ReAct loop，让模型通过 native tool calls 或 XML+JSON 文本协议返回 tool calls。
4. 执行白名单工具，将结构化 Observation 回填给模型。
5. 模型可以继续调用工具或输出 final answer，直到 final、重复调用保护或 `max_steps`。

主界面通过 SSE 消费同一条 Runtime 链路，实时展示路由、工具执行、Artifact 生成和最终回复增量；同步接口仍复用同一套 ReAct 逻辑。

模型失败、超时、非法 tool call 或未知工具时，API 返回错误，不自动降级 stub。只有未配置真实 LLM 时才使用 stub。

`SEMIDIAG_LLM_TOOL_MODE=prompt_xml_json` 用于未开启 auto-tool-choice 的部署。该模式不发送 `tools/tool_choice`，通过 `<available_tools>` 注入工具列表，通过 `<tool_calls>` / `<final_answer>` 做动作边界，但 Runtime 仍解析成统一的 `LLMToolCall` 并复用同一套工具执行链路。

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
- `build_trend_chart`: 使用 Matplotlib 生成趋势图 PNG 文件 Artifact。
- `diagnose_performance`: 基于 evidence 生成辅助诊断。
- `generate_report`: 使用 `ppt-template-sdk` 生成可下载的 PPTX 报告 Artifact。

## User Visible Artifacts

Agent 只在回复中总结图表和报告，不把内部 id 暴露给用户。WebUI 根据 Artifact 展示用户可见资产：

- `chart`: 多张 Matplotlib 图表，按 `display_group`、`figure_kind` 和 `order` 排序切换。
- `report`: PPTX 报告下载入口，同时展示结构化章节摘要。

后端通过 `/api/artifacts/{artifact_id}/file` 返回生成文件。该接口当前是内网开发版本，后续接入权限后应按案例权限校验访问。

## WebUI Workspace

主界面分为三个独立滚动区域：

- 左侧案例栏：案例名、上传数据、Trace 调试入口。
- 中间聊天区：消息列表独立滚动，输入区固定底部，展示流式 Agent 进度。
- 右侧诊断工作台：概览、图表、报告三类用户可见产物，不展示原始 Artifact 列表和工具轨迹。

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
- messages、tool mode 和工具清单。
- tool calls / response。
- 错误和耗时。

API key 和 Authorization header 不能进入审计记录。

Provider 负责各自的工具规格、消息编码、Observation 回填和模型输出解析；Runtime 只消费统一的 `LLMToolCall` 和最终回复，不判断具体工具协议。
LLM 公共 contract、prompt XML+JSON parser 和审计脱敏已拆到独立模块，`semidiag.agent.llm` 保持兼容导出入口。

独立 Trace 调试台按案例聚合 AgentStepTrace、ToolCallTrace 和 LLMAuditEvent，支持查看 timeline、展开脱敏 request/response，并导出脱敏 JSON。主诊断界面默认不请求 trace API。

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
