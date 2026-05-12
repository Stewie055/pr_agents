# Phase 3: Agent Memory, RAG, Workflow, And Tasks

## Goal

补齐成熟 Agent 产品需要的长期记忆、知识检索、异步任务和 Workflow 复用能力。

## Key Work

- 使用进程内任务队列实现解析、绘图、PPT、批处理等长任务的状态管理。
- 增加任务状态 API：pending、running、succeeded、failed、cancelled。
- Workflow 首版支持从一次诊断沉淀为步骤模板，并手动触发重放。
- 中期记忆持久化到 SQLite。
- 长期知识库提供抽象接口，默认本地实现支持文档摘要检索和来源引用。
- knowledge_qa 路径从通用回答升级为检索增强回答。

## Acceptance

- 长任务不阻塞主请求链路。
- Workflow 重放可生成新的 Tool traces 和 Artifacts。
- RAG 回答带来源摘要，不把完整原文塞给 LLM。
- 任务、Workflow、RAG 都有自动化测试。
