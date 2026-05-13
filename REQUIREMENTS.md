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
- 测校插件可以提供 Markdown Skill 文档，只有插件被选中时才注入 Agent 上下文。
- Tool 调用必须经过框架默认 guardrail，拦截跨案例数据、手填内部 ID 和缺少结构化输出的结果。
- 插件发现必须优先读取 manifest，不执行业务实现代码即可展示插件能力、工具、Skill、配置需求和状态。
- 绘图、PPT 报告等长耗时 Tool 必须通过任务队列执行，并通过 task id 暴露状态；任务记录必须持久化，服务重启后不得静默丢失运行中任务。
- 分析、诊断、报告路径必须提供用户可见流式进度，包括路由、工具调用、任务状态、产物生成和最终回复增量。
- 聊天、资料问答和 ReAct 最终回复必须实时转发 LLM delta，不允许在后端等待完整模型回复后一次性输出。
- Tool 返回必须包含面向 LLM 的结构化 Observation，不能只返回自然语言 summary。
- 系统自动选择当前案例最新上传的数据集，不要求用户手动提供 dataset id。
- 用户可见回复默认不暴露内部 case/dataset/artifact id。
- 高风险动作必须有人确认，包括代码执行、数据写入、Workflow 发布、正式报告发布和处置建议确认。
- Workflow 是核心能力，支持从一次诊断沉淀为可复用流程，并支持批处理和定时报告。
- LLM 内网/本地优先，敏感设备数据默认不出内网。
- 真实 LLM 通过 OpenAI-compatible `/v1/chat/completions` 接入，支持原生 tool calling 和 prompt-xml-json 文本工具协议两种模式。
- OpenAI-compatible LLMProvider 必须支持 `stream=true`，包括文本 delta、native tool-call delta 累积和 prompt-xml-json 文本流解析。
- LLM 上下文只发送案例摘要、Artifact 元数据、Evidence 和工具结果摘要，不发送原始文件行级数据。
- 完整记录 LLM prompt/request/response 审计内容，密钥和认证头不得落库。
- 系统必须提供独立 Trace 调试能力，能按案例查看路由、ReAct 步骤、工具调用、Observation、LLM 审计、耗时和错误，并支持脱敏导出；主诊断界面默认只展示用户可见信息。
- Trace 调试台默认展示聚合后的完整 LLM 回复和 tool calls，raw streaming chunks 只作为展开排查内容。
- 主诊断界面必须固定视口工作区，聊天区和右侧工作台独立滚动，避免长回复撑高整个页面。
- 业务图表由 Service 层使用 Matplotlib 或业务绘图库生成图片文件，Artifact 必须提供可下载/可预览的文件 URL；前端必须支持多图切换展示。
- 报告输出以 PPTX 为主，使用仓库内 vendored `ppt_template_sdk` 单文件模板渲染，不依赖私有 Git 仓库；报告 Artifact 必须包含格式、MIME、文件 URL 和结构化章节摘要。
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
- Generic/LT equipment metadata plugin。
- 通用 CSV file analysis service under `business/services` and plugin-scoped CSV tools under `business/plugins`。
- 生产运行时仅支持 OpenAI-compatible LLM provider；自动化测试使用测试专用 fake provider。
- Native tools / prompt-xml-json LLM tool mode。
- LLMProvider streaming and Agent SSE event stream。
- LLM prompt/request/response audit。
- LLM Router/Triage and deterministic State Gate。
- ReAct multi-step tool loop and AgentStepTrace；同步和流式路径共享同一套 step executor。
- Trace debug API and WebUI debug console。
- Stream-first WebUI with independent chat scrolling and right-side diagnostic workspace。
- Matplotlib PNG chart artifacts and chart gallery。
- PPTX report artifacts with vendored `ppt_template_sdk` integration and file download API。
- Agent runtime and Tool Registry。
- Artifact/Evidence/DiagnosisConclusion 数据模型。
- Backend and frontend tests.
- Product maturity plans under `plans/`.
- CI quality gate covering backend lint/tests and frontend typecheck/tests/build.
- Diagnostic plugin registry with `equipment_type` based plugin resolution.
- Structured metric repository contract with SQLite default implementation and ClickHouse adapter target.
- SQLite-persisted task records with an in-process task executor and task status API for long-running analysis, chart, report, and workflow jobs.
- Midterm memory persisted in SQLite and loaded into LLM case context.
- Local knowledge records with keyword retrieval for knowledge_qa context, keeping vector RAG replaceable later.
- Workflow template foundation with case trace capture and manual replay API.
- Business extension loader for `business/tools/*.py` and manifest-first `business/plugins/<plugin_name>/plugin.json`; business services live under `business/services`.
- LT calibration plugin manifests and plugin-scoped tool exposure to avoid tool explosion.
- Markdown Skill loader for selected calibration plugins.
- Default Tool Guardrail for dataset ownership, system-managed dataset id, and structured ToolResult validation.
- Manifest-first directory plugin packages under `business/plugins/<plugin_name>/`.
- Async task ToolResult for CSV chart and PPT report tools.
- LT log pool metadata detected from filename rules for LT-D, LT-C, and LT-R.

## Non-Goals For Current Slice

- 不接入真实保密业务代码。
- 不绑定具体商业 LLM SDK。
- 不实现 ClickHouse 写入。
- 不实现生产级权限系统和审批流。
- 不执行 Agent 生成代码。
