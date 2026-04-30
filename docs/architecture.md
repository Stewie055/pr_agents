# 架构说明

## 分层

当前实现按变化方向分层，而不是按概念堆层：

```text
WebUI
  -> REST API / SSE API
  -> Application Services
  -> Agent Runtime
  -> Agent Tools
  -> Use Cases / Task Service
  -> Business Capabilities / Stub Adapters
  -> Repositories / File Artifact Store
```

## WebUI

正式入口是 `React + Vite + TypeScript` 科研实验室风格工作台。

职责：

- CSV 上传、SQL source 注册和显式 source 选择
- fake/LLM 模型模式切换
- 会话消息和 prompt 输入
- Agent 工具步骤、后台任务状态、artifact 预览
- 报告、图表图片、表格结果展示
- 取消当前任务

## API

REST 管理资源，SSE 推送运行过程。

- REST：session、source、message、task、artifact、cancel
- SSE：run started、tool called、task queued、task status、artifact ready、assistant completed、run completed

## Agent Runtime

第一阶段采用单一 ReAct Agent。

职责：

- 构建 PydanticAI Agent
- 注册薄 tool
- 运行一次 Agent run
- 推送 run/tool/task/assistant 事件
- 在 LLM 模式失败时回退 fake

不承担：

- CSV 解析
- SQL 执行
- 图表生成
- 报告生成
- 业务参数决策

## Agent Tools

主工具：

- `analyze_source`
- `load_latest_report`
- `summarize_report`
- `cancel_task`

兼容保留：

- `run_file_analysis_workflow`
- `run_db_analysis_workflow`

Tool 只做 schema 暴露和 use case 调用，业务规则在 application/service 层。

## Application Services

`AgentSessionService`：

- 创建 session
- 记录消息
- 注册 CSV/SQL/demo source
- 启动 Agent run
- 格式化 SSE

`TaskApplicationService`：

- 创建任务
- 后台异步执行
- 取消任务
- 持久化结果和 artifact
- 提供任务查询和 artifact 读取

## Business Capabilities

`StubAnalysisPlatform` 模拟 QT 业务：

- CSV 解析或 SQL 模拟查询
- 数据清洗标记
- 指标分析
- SVG 图表图片生成
- 结构化 Markdown 报告生成

后续接真实 QT 代码时，应替换 capability adapter，而不是改 Agent Runtime。

## Infrastructure

- SQLite：session、message、source、run、run step、task、artifact、task result
- Local files：CSV upload、table artifact、chart SVG、report markdown

## 设计约束

- 数据源必须显式选择，不再自动使用最新 source。
- 缺 source 是 clarification，不是 workflow failure。
- Planner/RAG/长期 memory 不进入第一阶段。
- 单进程后台队列只用于开发雏形，生产可替换为 Celery/Redis/任务服务。
