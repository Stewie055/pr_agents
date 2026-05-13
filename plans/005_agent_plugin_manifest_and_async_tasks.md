# Phase 5: Agent Plugin Manifest And Async Tasks

## Goal

把插件系统从“导入代码后注册”升级为 manifest-first discovery，并把耗时图表/报告工具接入任务队列。

## TODO Backlog

- Plugin manifest-only discovery：不执行插件实现即可发现插件、工具、Skill、配置需求和状态。
- Plugin status/config validation：`requires_config` 缺失时标记 degraded，并阻止工具进入 active registry。
- Skill selection：按用户问题、日志类型、场景和 triggers 选择 Skill，避免选中插件后注入全部 Skill。
- Plugin/tool guardrails：支持插件级和工具级自定义 guardrail。
- Async task tools：解析、绘图、PPT、重分析等长耗时工具通过任务队列执行；Runtime 持久化 continuation，任务完成后把结果回注为 observation 并续跑 Agent。
- Tool selection：在插件被选中后继续裁剪工具，避免单插件工具过多。
- Router/selector repair：LLM JSON 解析失败时执行一次修复重试，并加入低置信度澄清。
- Runtime convergence：同步和流式 ReAct 共享同一个 step executor，避免行为漂移。
- ContextBuilder：统一管理 memory、RAG、Skill、Artifact、Evidence 的 token budget 和可见字段。
- Trace UX：突出展示插件选择、Skill 注入、Guardrail 失败、任务状态。
- Workflow maturity：从 trace replay 升级为有版本、参数映射、依赖和任务化执行的 workflow graph。
- Runtime schema validation：对 Tool input/output schema 做运行时校验。
- Token/cost accounting：记录 LLM usage、cost 和延迟统计。
- Plugin/Skill management UI：展示插件状态、配置缺失、Skill 列表和加载错误。
- File classifier maturity：支持多规则优先级、内容 sniff、冲突解释和人工修正 metadata。

## Remaining Product Gaps

- Runtime convergence：同步和流式 ReAct 仍存在重复执行逻辑，后续工具错误、任务事件和 trace 改动容易漂移。
- True token streaming：chat_response、knowledge_qa 和 ReAct final-answer 必须边接收 LLM delta 边发送 SSE，不能先聚合再输出。
- Trace readability：调试台默认展示聚合后的完整 LLM 回复，raw streaming chunks 只作为展开排查内容。
- Tool/Skill selection：选中插件后还需要按当前问题继续裁剪 tool/skill，避免单插件工具过多。
- RAG memory maturity：长期记忆仍是关键词检索，需要 embedding/RAG、来源版本和 token budget。
- Runtime schema validation：Tool input/output schema 还未做运行时校验。
- Token/cost accounting：LLM usage、cost、latency 还未进入审计统计。
- Plugin management UI：插件状态、配置缺失、Skill 和加载错误还没有独立管理视图。

## Current Priority

1. Plugin manifest-only discovery with directory-style plugin packages.
2. Async task tools for chart generation and PPT report generation.
3. ReAct runtime convergence: non-streaming and streaming paths share one step executor.
4. Persistent task UX: task records are stored in SQLite, exposed by case, and refreshed in the WebUI.
5. True token streaming and readable LLM trace summaries.

## Acceptance

- `/api/calibrations` 能展示 manifest 发现的插件、工具、Skill、状态和配置错误。
- 配置缺失的插件不进入 Agent active tool registry。
- 图表和报告工具返回 task 引用，任务完成后生成 Artifact。
- README、REQUIREMENTS 和 docs 同步更新。
- 后端测试、前端测试和构建通过。
- 同步和流式 Agent 对同一工具链路产生一致的 tool trace、artifact 和 final message metadata。
- 服务重启后 pending/running task 被标记为 interrupted/failed，不静默丢失。
- 前端能展示当前案例任务状态，任务完成后自动刷新图表/PPT。
- Runtime 能在任务终态后自动恢复 waiting continuation，并继续 ReAct 直到最终回复或下一次异步任务边界。
