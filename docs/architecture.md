# Architecture

## Layering

```text
Vue/Vite WebUI
  -> FastAPI API
  -> Agent Runtime / Workflow Orchestration
  -> Tool Registry
  -> Business Services
  -> Infrastructure
```

## Key Boundaries

- WebUI 只展示诊断案例、对话、工具轨迹、Artifact 和报告，不承载业务算法。
- API 负责请求编排、认证扩展点和 DTO 转换。
- Agent Runtime 负责意图理解、工具选择、上下文整理和结果总结。
- Tool 是薄适配层，负责 schema、权限、审计和 Service 调用。
- Business Service 位于 `business/services`，实现解析、清洗、统计、建模、Matplotlib 绘图、规则诊断和 PPT 报告生成。
- Infrastructure 提供 SQLite、原始文件存储、生成文件存储、未来 ClickHouse、RAG 和任务队列适配。
- 结构化指标通过 `MetricRepository` 写入，当前默认 SQLite 实现用于本地开发和测试，后续 ClickHouse adapter 应实现同一接口。
- 长任务通过 `InProcessTaskQueue` 起步，当前提供任务状态 API；后续解析、绘图、PPT 和 Workflow 批处理逐步迁移到任务队列。
- 业务扩展通过 `business/tools`、`business/plugins` 和 `business/services` 组织。公共工具启动时进入 common registry；测校插件启动时只进入 manifest catalog，被选中后才构建 plugin tools。

## Diagnostic Case

诊断案例是长期主工作区。一次案例包含：

- 设备类型和状态。
- 上传文件或历史数据引用。
- Agent 对话和中期记忆。
- 工具调用轨迹。
- 结构化 Artifact。
- 图表和报告文件 Artifact。
- Evidence 证据链。
- DiagnosisConclusion 辅助结论。
- 报告草稿和发布审计。

中期记忆以 `MemoryRecord` 持久化到 SQLite，当前用于保存案例级摘要；长期记忆和 RAG 后续通过独立知识库接口扩展。

## Extension Model

业务能力通过 `business` 扩展包提供。扩展包应提供：

- 数据解析器。
- 指标定义和派生指标。
- 规则和阈值。
- 统计/模型诊断逻辑。
- Tool 声明。
- Matplotlib 或业务绘图库图表生成器。
- `ppt-template-sdk` 报告模板。
- 知识库索引配置。

当前实现提供 `GenericEquipmentPlugin` 作为打桩示例。
`GenericEquipmentPlugin` 和 `LTEquipmentPlugin` 只保留设备元数据；真实业务能力由 `business/plugins` 注册并按 manifest 选择，不应改 Agent 或 Tool 核心逻辑。
