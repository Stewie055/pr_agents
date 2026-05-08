# Requirements

## Product Goal

建设企业内网部署的半导体设备性能诊断 Agent 平台。系统通过对设备日志、性能文件和历史指标进行解析、统计、建模、知识检索和报告生成，辅助设备/工艺工程师完成性能异常分析。

## Long-Term Requirements

- 以诊断案例为核心工作单元，聚合数据、对话、证据、结论、报告和审计。
- 支持设备类型诊断插件包，包括解析器、指标定义、规则、模型、工具、报告模板和知识索引配置。
- Agent 提供辅助诊断能力，输出可能原因、置信度、风险等级、证据链和建议动作。
- 高风险动作必须有人确认，包括代码执行、数据写入、Workflow 发布、正式报告发布和处置建议确认。
- Workflow 是核心能力，支持从一次诊断沉淀为可复用流程，并支持批处理和定时报告。
- LLM 内网/本地优先，敏感设备数据默认不出内网。
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
- Agent runtime and Tool Registry。
- Artifact/Evidence/DiagnosisConclusion 数据模型。
- Backend and frontend tests.

## Non-Goals For Current Slice

- 不接入真实保密业务代码。
- 不实现真实 LLM provider。
- 不实现 ClickHouse 写入。
- 不实现生产级权限系统和审批流。
- 不执行 Agent 生成代码。
