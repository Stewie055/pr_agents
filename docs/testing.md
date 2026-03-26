# 测试说明

当前自动化测试覆盖：

- 模型和 Service 接口契约
- Workflow 编排
- Tool 调用
- Agent Orchestration 路由
- WebUI 端到端闭环
- API 提交、查询、artifact 读取
- SQLite 持久化与失败状态流转
- A 类单业务单文件和 B 类共享文件示例
- `scientific_plot` 图表产物示例
- 官方 `A_DEMO` demo 闭环示例
- Agent 会话 API、多轮追问和 WebUI 首页示例
- 聊天式布局、会话列表和底部输入区示例
- 服务重启后的任务结果恢复示例
- `FakeLLM` 与 `GLMProvider` 示例
- fake / llm 双模切换与 fallback 示例
- GLM provider 请求构造与 provider 未配置 fallback 示例
- 普通聊天不触发工具的 session 示例
- 单个 `PydanticAI Agent` 的 workflow-level 工具决策和 run/step 轨迹示例
- `MemoryManager` 的最近任务与最近报告摘要示例
- SSE run 启动、事件流顺序和 session 最终一致性示例
- `assistant_started / assistant_delta / assistant_completed` 的增量回复示例
- WebUI “运行中独立工具卡片区 + 完成后折叠 Task details” 展示示例
- 双主线 demo：文件分析、数据库分析，以及报告摘要追问示例

## 运行

```bash
uv run pytest
```

## 测试策略

- 通过 stub service 确保当前仓库无需 QT 代码即可完成最小闭环验证。
- 后续接入 QT 真实实现后，应保留现有契约测试并新增适配器测试。
