# Architecture

## Layering

```text
Vue/Vite WebUI
  -> FastAPI API
  -> Agent Runtime / Workflow Orchestration
  -> Tool Registry
  -> Diagnostic Services
  -> Infrastructure
```

## Key Boundaries

- WebUI 只展示诊断案例、对话、工具轨迹、Artifact 和报告，不承载业务算法。
- API 负责请求编排、认证扩展点和 DTO 转换。
- Agent Runtime 负责意图理解、工具选择、上下文整理和结果总结。
- Tool 是薄适配层，负责 schema、权限、审计和 Service 调用。
- Service 层实现解析、清洗、统计、建模、规则诊断和报告生成。
- Infrastructure 提供 SQLite、文件存储、未来 ClickHouse、RAG 和任务队列适配。

## Diagnostic Case

诊断案例是长期主工作区。一次案例包含：

- 设备类型和状态。
- 上传文件或历史数据引用。
- Agent 对话和中期记忆。
- 工具调用轨迹。
- 结构化 Artifact。
- Evidence 证据链。
- DiagnosisConclusion 辅助结论。
- 报告草稿和发布审计。

## Extension Model

设备类型通过诊断插件包扩展。插件包应提供：

- 数据解析器。
- 指标定义和派生指标。
- 规则和阈值。
- 统计/模型诊断逻辑。
- Tool 声明。
- 报告模板。
- 知识库索引配置。

当前实现提供 `GenericEquipmentPlugin` 作为打桩示例。
