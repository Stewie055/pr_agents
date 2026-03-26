# plans

## 已完成的第一阶段

- 建立 Python 项目骨架和依赖声明。
- 定义统一 Pydantic 数据模型与错误模型。
- 建立 `Service` 接口和 stub 实现。
- 建立三条主工作流：
  - 文件分析
  - 数据库分析
  - 基于已有产物生成报告
- 建立 Tool 层与最小 PydanticAI Agent 封装。
- 建立 WebUI 门面接口。
- 建立自动化测试与文档。

## 已完成的第二阶段

- 增加 FastAPI API 入口。
- 增加 SQLite 持久化仓储，保存 session、task、artifact 元数据。
- 增加任务应用服务和同步执行状态流转。
- 增加 API、持久化、失败场景测试。

## 已完成的第三阶段

- 在文件和数据库分析入口中引入 `business_code` 统一业务标识。
- 为通用接口补充 `source_profile`、`clean_profile`、`analysis_profile`、`chart_profile`、`report_profile`。
- 用 stub 实现 A 类单业务单文件和 B 类共享文件两种分派示例。
- 将 matplotlib 科学绘图统一收敛到 `ChartArtifact`，通过 `chart_type=scientific_plot` 区分。
- 增加共享文件和科学绘图场景的自动化测试。

## 已完成的第四阶段

- 补充官方 `A_DEMO` HTTP API demo 路径。
- 新增 demo 样例数据和独立演示文档。
- 在 README 中增加 Run Demo 入口。
- 增加官方 demo 闭环回归测试。

## 第五阶段计划与实现

- 增加聊天式 Agent 会话服务，而不是仅提供表单/API demo。
- 增加 Agent session API：创建会话、发送消息、读取会话状态和报告内容。
- 在 FastAPI 根路径提供单页 WebUI，展示 Agent 计划、工具调用和结果。
- 支持官方 `A_DEMO` 快捷按钮和多轮追问“重新查看报告”。
- 增加会话消息持久化与 WebUI/Agent 会话测试。

## 第六阶段计划与实现

- 将 WebUI 从“调试型 demo 面板”重做为对话优先的聊天布局。
- 增加左侧会话列表、`New chat` 入口和当前会话标题。
- 将输入区固定在主区底部，并支持 Enter 发送、Shift+Enter 换行。
- 将计划和工具调用降级为可展开的执行卡片，而不是主消息流中的大块文本。
- 保留 `Run A_DEMO` 快捷入口，但使其融入聊天交互。

## 下一阶段建议

- 增加真实 QT Service 适配器。
- 增加会话恢复和异步任务执行。
- 增加长期知识库与 RAG 读取。
- 增强 Agent 的真实 Planner / Memory / RAG 能力。
