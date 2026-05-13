# Phase 3: Agent Memory, RAG, Workflow, And Tasks

## Goal

补齐成熟 Agent 产品需要的长期记忆、知识检索、异步任务和 Workflow 复用能力。

## Key Work

- 使用进程内 worker 执行解析、绘图、PPT、批处理等长任务，任务记录持久化到 SQLite。当前 `InProcessTaskQueue(repository=...)` 基础设施已完成。
- 增加任务状态 API：pending、running、succeeded、failed、cancelled、interrupted。当前 `GET /api/tasks`、`GET /api/tasks?case_id=...`、`GET /api/tasks/{task_id}` 和取消接口已完成。
- 图表生成和 PPT 报告生成已作为首批任务型工具接入任务队列。
- 前端工作台已展示当前案例任务，并在任务完成后自动刷新图表/PPT Artifact。
- Workflow 首版支持从一次诊断沉淀为步骤模板，并手动触发重放。当前 Tool trace 到 `WorkflowTemplate` 以及手动重放 API 已完成。
- 中期记忆持久化到 SQLite。当前 `MemoryRecord` 和 `MemoryService(repository)` 已完成。
- 长期知识库提供抽象接口，默认本地实现支持文档摘要检索和来源引用。当前 SQLite 本地知识记录和关键词检索 API 已完成。
- knowledge_qa 路径从通用回答升级为检索增强回答。当前会把知识命中摘要放入非工具 LLM 上下文。

## Acceptance

- 长任务不阻塞主请求链路。
- Workflow 重放可生成新的 Tool traces 和 Artifacts。
- RAG 回答带来源摘要，不把完整原文塞给 LLM。
- 任务、Workflow、RAG 都有自动化测试。
