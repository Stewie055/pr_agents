# 测试说明

当前自动化测试覆盖：

- 模型和 Service 接口契约
- Workflow 编排
- Tool 调用
- Agent Orchestration 路由
- WebUI 端到端闭环
- API 提交、查询、artifact 读取
- SQLite 持久化与失败状态流转

## 运行

```bash
uv run pytest
```

## 测试策略

- 通过 stub service 确保当前仓库无需 QT 代码即可完成最小闭环验证。
- 后续接入 QT 真实实现后，应保留现有契约测试并新增适配器测试。
