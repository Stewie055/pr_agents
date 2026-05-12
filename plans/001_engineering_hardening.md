# Phase 1: Engineering Hardening

## Goal

降低后续扩展成本，把 Agent Runtime、LLM Provider 和质量门禁整理到可持续演进的结构。

## Key Work

- 拆分 LLM 层：公共 contract、prompt XML+JSON parser 和 audit redaction 独立维护；后续继续拆 OpenAI HTTP client 与 native tool protocol。
- 拆分 Agent Runtime：同步和流式 ReAct 共享工具执行、Observation、停止条件和最终消息持久化逻辑。
- 增加工程质量命令：后端测试、前端测试、前端构建、静态检查入口。
- 增加 CI，覆盖后端 pytest、前端 Vitest 和前端 build。
- 当前质量门禁入口为 `bash scripts/check.sh`，CI 位于 `.github/workflows/ci.yml`。
- 文档明确质量门禁和本地验证命令。

## Acceptance

- 现有 API 行为不变。
- 所有现有测试通过。
- 新增质量命令能在本地运行。
- CI 文件可直接在 GitHub Actions 上执行。
