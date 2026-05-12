# Phase 1: Engineering Hardening

## Goal

降低后续扩展成本，把 Agent Runtime、LLM Provider 和质量门禁整理到可持续演进的结构。

## Key Work

- 拆分 LLM 层：OpenAI HTTP client、native tool protocol、prompt XML+JSON protocol、parser 和 audit redaction 独立维护。
- 拆分 Agent Runtime：同步和流式 ReAct 共享工具执行、Observation、停止条件和最终消息持久化逻辑。
- 增加工程质量命令：后端测试、前端测试、前端构建、静态检查入口。
- 增加 CI，覆盖后端 pytest、前端 Vitest 和前端 build。
- 文档明确质量门禁和本地验证命令。

## Acceptance

- 现有 API 行为不变。
- 所有现有测试通过。
- 新增质量命令能在本地运行。
- CI 文件可直接在 GitHub Actions 上执行。
