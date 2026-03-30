# 测试说明

当前自动化测试覆盖：

- Service 接口契约与 stub 行为
- Workflow 编排
- Tool 调用
- `AnalysisExecutionService` 与 `TaskApplicationService` 执行链路
- API 提交、查询、artifact 读取
- SQLite 持久化与失败状态流转
- session source 注册、查询与 demo source 注入
- `ReAct` 单 Agent 的 workflow-level 工具决策
- 无 source 引导、多轮追问、报告重看与报告摘要
- `llm` 运行时模型失败回退到 `fake`
- SSE 事件流与 session 最终一致性
- React 组件渲染与前端构建

## 运行

```bash
uv run pytest
cd frontend && pnpm test
cd frontend && pnpm build
```

## 当前门槛

- 后端测试必须通过
- 前端测试必须通过
- 前端生产构建必须通过

## 策略

- 当前仍通过 stub service 保证仓库在无 QT 代码时可回归
- 后续接入 QT 真实实现后，应保留现有契约测试并新增适配器测试
- 长期记忆、RAG、Planner 相关测试不在第一阶段范围内
