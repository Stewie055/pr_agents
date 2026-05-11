# Requirements

## Product Goal

建设企业内网部署的半导体设备性能诊断 Agent 平台。系统通过对设备日志、性能文件和历史指标进行解析、统计、建模、知识检索和报告生成，辅助设备/工艺工程师完成性能异常分析。

## Long-Term Requirements

- 以诊断案例为核心工作单元，聚合数据、对话、证据、结论、报告和审计。
- 支持设备类型诊断插件包，包括解析器、指标定义、规则、模型、工具、报告模板和知识索引配置。
- Agent 提供辅助诊断能力，输出可能原因、置信度、风险等级、证据链和建议动作。
- Agent 必须先通过 LLM Router/Triage 理解用户意图，支持聊天、资料问答、数据分析、诊断、报告和 Workflow 请求等路径。
- 系统本地 State Gate 只负责确定性约束，例如是否已有数据集、工具是否可用、是否需要审批。
- 分析、诊断、报告路径必须使用 ReAct/Graph 执行模型，允许多轮工具调用、观察和继续推理。
- Tool 返回必须包含面向 LLM 的结构化 Observation，不能只返回自然语言 summary。
- 系统自动选择当前案例最新上传的数据集，不要求用户手动提供 dataset id。
- 用户可见回复默认不暴露内部 case/dataset/artifact id。
- 高风险动作必须有人确认，包括代码执行、数据写入、Workflow 发布、正式报告发布和处置建议确认。
- Workflow 是核心能力，支持从一次诊断沉淀为可复用流程，并支持批处理和定时报告。
- LLM 内网/本地优先，敏感设备数据默认不出内网。
- 真实 LLM 通过 OpenAI-compatible `/v1/chat/completions` 接入，支持原生 tool calling 和 prompt-json 文本工具协议两种模式。
- LLM 上下文只发送案例摘要、Artifact 元数据、Evidence 和工具结果摘要，不发送原始文件行级数据。
- 完整记录 LLM prompt/request/response 审计内容，密钥和认证头不得落库。
- 系统必须提供 Trace 调试能力，能按案例查看路由、ReAct 步骤、工具调用、Observation、LLM 审计、耗时和错误，并支持脱敏导出。
- 原始文件保留版本，结构化性能指标长期进入 ClickHouse。
- 元数据先用 SQLite 起步，并保持 PostgreSQL 迁移兼容。
- RAG 通过抽象接口接入，长期支持可替换向量库。
- 每次功能变更必须补充自动化测试、执行测试并同步更新文档。

## Current Implementation Scope

- 独立工程骨架。
- FastAPI API。
- Vue/Vite 前端。
- SQLite repository。
- Local file store。
- Generic equipment diagnostic plugin。
- CSV demo diagnostic service。
- Stub LLM provider。
- OpenAI-compatible LLM provider。
- Native tools / prompt-json LLM tool mode。
- LLM prompt/request/response audit。
- LLM Router/Triage and deterministic State Gate。
- ReAct multi-step tool loop and AgentStepTrace。
- Trace debug API and WebUI debug console。
- Agent runtime and Tool Registry。
- Artifact/Evidence/DiagnosisConclusion 数据模型。
- Backend and frontend tests.

## Non-Goals For Current Slice

- 不接入真实保密业务代码。
- 不绑定具体商业 LLM SDK。
- 不实现 ClickHouse 写入。
- 不实现生产级权限系统和审批流。
- 不执行 Agent 生成代码。
