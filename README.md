# Semiconductor Diagnostic Agent

面向半导体工业设备性能数据的 Agent 化辅助诊断平台。系统围绕诊断案例组织数据、对话、工具调用、证据链、结论和报告，目标是帮助设备/工艺工程师分析性能异常并生成可审阅报告。

## Current Capabilities

- FastAPI 后端 API
- Vue/Vite 前端诊断案例工作区
- SQLite 元数据、会话、工具轨迹和 Artifact 存储
- 本地设备性能文件上传
- 可插拔诊断插件包骨架
- Stub LLM / OpenAI-compatible LLM + Agent runtime + Tool Registry
- LLM Router/Triage，根据用户问题选择聊天、资料问答、数据分析、诊断或报告路径
- State Gate，自动检查当前案例是否已有数据，缺数据时提示上传
- ReAct 多步工具循环，支持观察工具结果后继续分析直到形成最终回复
- LLM 工具调用支持 native tools 与 prompt-xml-json 文本协议两种模式
- Trace 调试台，可查看 ReAct 步骤、工具轨迹、LLM 审计并导出脱敏 JSON
- 通用 CSV 性能数据示例诊断
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

长期设计以设备类型诊断插件扩展业务能力。Agent 只负责编排和总结，不直接承载业务算法；真实解析、清洗、统计、建模、报告能力应沉到 Service 层。

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd frontend
npm install
```

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

不想连接真实模型时，把 `SEMIDIAG_LLM_PROVIDER` 改成 `stub`。

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

## Demo Flow

1. 在 WebUI 创建诊断案例。
2. 上传包含数值指标的设备性能 CSV。
3. 发送“请分析这份设备性能数据，给出诊断、证据和建议”。
4. Agent 通过 ReAct loop 调用字段检查、画像、趋势图、诊断等工具。
5. WebUI 展示工具轨迹、Artifact、证据和报告草稿。
6. 需要排查 Agent 行为时，在右侧 Trace 调试台刷新步骤，或导出脱敏 JSON。

Agent 会自动使用当前案例最新上传的数据集。界面和回复默认不展示内部 case/dataset/artifact id，也不会要求用户手动输入 dataset id。

## Documentation

- [Requirements](REQUIREMENTS.md)
- [Architecture](docs/architecture.md)
- [Agent Design](docs/agent_design.md)
- [Service and Tool Contract](docs/service_tool_contract.md)
- [Development Guide](docs/dev_guide.md)
- [LLM Provider](docs/llm_provider.md)
- [ReAct Agent Loop](docs/react_agent_loop.md)
