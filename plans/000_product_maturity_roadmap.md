# Product Maturity Roadmap

## Goal

把当前 Alpha 技术验证版推进为可接入真实半导体设备诊断业务的产品底座。路线以工程硬化优先，随后补齐数据平台、插件体系、异步任务、Workflow、RAG、前端产品体验和运维能力。

## Execution Rules

- 每个阶段或可独立验证的子阶段完成后单独提交 Git。
- 每次功能变更必须补充自动化测试，并执行对应测试。
- 每次行为或设计变化必须同步更新 `README.md`、`REQUIREMENTS.md` 和 `docs/`。
- 权限系统本阶段不实现，只保留 `actor`、审计和未来外部系统接入点。
- 不考虑旧版本兼容，优先做最优结构和完整能力。

## Phases

1. Engineering hardening: 拆分 Runtime/LLM、增加质量门禁和 CI。
2. Data and plugin platform: 插件注册模型、指标 schema、ClickHouse 抽象、正式 Service/Tool contract。
3. Async task and Workflow: 进程内任务队列、任务状态 API、Workflow 模板与重放。
4. Memory and RAG: 中期记忆持久化、长期知识库抽象、检索增强问答。
5. Product UI and operations: 案例管理、任务视图、产物版本、Trace 增强、日志和部署。

## Done Criteria

- 主链路保持可运行：上传数据、Agent 分析、图表、PPT、Trace。
- 后端测试、前端测试和前端构建通过。
- 新能力具备可替换接口，不把真实保密业务逻辑写死在 Agent 或 WebUI。
- 工程结构能支撑后续多 Agent、Workflow 和真实业务插件扩展。
