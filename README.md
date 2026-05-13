# Semiconductor Diagnostic Agent

面向半导体工业设备性能数据的 Agent 化辅助诊断平台。系统围绕诊断案例组织数据、对话、工具调用、证据链、结论和报告，目标是帮助设备/工艺工程师分析性能异常并生成可审阅报告。

## Current Capabilities

- FastAPI 后端 API
- Vue/Vite 前端诊断案例工作区
- SQLite 元数据、会话、工具轨迹和 Artifact 存储
- SQLite 结构化指标仓储抽象，后续可替换为 ClickHouse adapter
- 本地设备性能文件上传
- 可插拔诊断插件包骨架
- 诊断插件注册表，可按案例 `equipment_type` 选择业务插件
- SQLite 持久化任务记录、进程内任务执行器和任务状态查询 API
- Workflow 模板基础，可从案例工具轨迹沉淀并手动重放
- 仓库内 `business/` 扩展加载，支持业务 Tool 和 LT 测校项目录式 Plugin
- Plugin-scoped tools：Agent 每轮只看到公共工具和被选中测校项插件提供的工具
- Manifest-first plugin discovery：通过 `plugin.json` 发现插件能力、配置需求、工具和 Skill
- Plugin Markdown Skills：被选中插件的业务分析指导按需进入 ReAct prompt
- Tool Guardrails：统一拦截跨案例数据、手填内部 dataset id 和缺少结构化输出的工具结果
- 异步任务型工具：图表生成和 PPT 报告生成通过任务队列执行，Runtime 持久化 continuation、轮询任务终态，并把任务结果作为 observation 续跑 Agent
- OpenAI-compatible LLM + Agent runtime + Tool Registry
- LLM Router/Triage，根据用户问题选择聊天、资料问答、数据分析、诊断或报告路径
- SQLite 持久化中期记忆摘要
- 本地知识库记录和关键词检索 API，供资料问答路径使用
- State Gate，自动检查当前案例是否已有数据，缺数据时提示上传
- ReAct 多步工具循环，支持观察工具结果后继续分析直到形成最终回复；同步和流式接口共享同一套 step executor
- SSE Agent 事件流，实时展示路由、工具调用、产物生成和回复增量
- 非工具聊天和 ReAct 最终回复均按 LLM delta 实时输出，不等待完整回复生成
- LLM 工具调用支持 native tools 与 prompt-xml-json 文本协议两种模式
- OpenAI-compatible LLMProvider 支持 `stream=true` token 增量输出和 streaming tool-call 累积；前端对 assistant 临时消息按 delta 做响应式更新，避免等 final 事件一次性刷新
- 独立 Trace 调试台，可查看 ReAct 步骤、异步 continuation、工具轨迹、聚合后的 LLM 审计摘要并导出脱敏 JSON
- 通用 CSV 文件分析、绘图、诊断和 PPT 报告插件
- Matplotlib PNG 图表 Artifact，多图图库、下载和全屏预览
- PPTX 诊断报告 Artifact，优先使用 `ppt-template-sdk` 模板渲染并支持下载
- 结构化 Artifact、Evidence、DiagnosisConclusion 和报告草稿
- 后端 pytest 与前端 Vitest 自动化测试

## Architecture

```text
WebUI
  -> API / Gateway
  -> Agent + Workflow Orchestration
  -> Tool Registry
  -> Service Layer
  -> Infrastructure
```

长期设计以业务扩展包提供诊断能力。Agent 只负责编排和总结，不直接承载业务算法；真实解析、清洗、统计、建模、绘图、报告能力应沉到 `business/services`，再由 `business/plugins` 或 `business/tools` 暴露为 Agent 可调用工具。

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd frontend
npm install
```

PPT 报告使用仓库内 vendored 单文件 `ppt_template_sdk`：

```text
src/semidiag/vendor/ppt_template_sdk.py
```

运行环境不需要访问私有 Git 仓库。该单文件 SDK 依赖 `python-pptx`，正式业务模板仍按 `ph:<type>:<key>` 占位符协议渲染。

## Run

复制并按需修改 LLM 配置：

```bash
cp .env.example .env
```

`.env.example` 默认按 DeepSeek V4 Flash 配置，本地运行前复制后填写 API key：

```bash
cp .env.example .env
```

```bash
SEMIDIAG_LLM_PROVIDER=openai_compatible
SEMIDIAG_LLM_TOOL_MODE=native
SEMIDIAG_LLM_BASE_URL=https://api.deepseek.com
SEMIDIAG_LLM_MODEL=deepseek-v4-flash
SEMIDIAG_LLM_API_KEY=fill-your-deepseek-api-key
```

生产运行时不再提供离线 stub provider；本地开发也需要配置 OpenAI-compatible LLM。自动化测试使用测试专用 fake provider，不依赖真实密钥。

如果模型部署不支持 OpenAI `tools/tool_choice`，把 `SEMIDIAG_LLM_TOOL_MODE` 改成 `prompt_xml_json`。该模式不会向 LLM 请求体发送 `tools` 字段，而是用 XML 标签做动作边界、JSON 承载工具列表和参数，驱动同一个 ReAct loop。

后端：

```bash
source .venv/bin/activate
semidiag-api
```

前端：

```bash
cd frontend
npm run dev
```

访问 `http://127.0.0.1:5173`。

默认开发服务绑定 `0.0.0.0`，同一内网机器可通过服务器 IP 访问：

- 后端：`http://<server-ip>:8000`
- 前端：`http://<server-ip>:5173`

## Tests

```bash
source .venv/bin/activate
python -m pytest

cd frontend
npm test
npm run build
```

Full local quality gate:

```bash
bash scripts/check.sh
```

## CSV Analysis Flow

1. 在 WebUI 创建诊断案例。
2. 上传包含数值指标的设备性能 CSV。
3. 发送“请分析这份设备性能数据，给出诊断、证据和建议”。
4. Agent 通过 SSE 实时展示路由、工具调用、图表/报告产物生成和回复增量。
5. WebUI 中间聊天区独立滚动，右侧诊断工作台展示概览、Matplotlib 图表和 PPT 报告入口。
6. 需要排查 Agent 行为时，从案例侧边栏打开“调试 Trace”进入独立调试台，或导出脱敏 JSON。

Agent 会自动使用当前案例最新上传的数据集。界面和回复默认不展示内部 case/dataset/artifact id，也不会要求用户手动输入 dataset id。

## Documentation

- [Requirements](REQUIREMENTS.md)
- [Architecture](docs/architecture.md)
- [Agent Design](docs/agent_design.md)
- [Service and Tool Contract](docs/service_tool_contract.md)
- [Extension Development](docs/extension_development.md)
- [LT Business Design](docs/lt_business_design.md)
- [Development Guide](docs/dev_guide.md)
- [LLM Provider](docs/llm_provider.md)
- [ReAct Agent Loop](docs/react_agent_loop.md)
- [Product Maturity Roadmap](plans/000_product_maturity_roadmap.md)
