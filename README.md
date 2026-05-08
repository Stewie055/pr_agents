# Semiconductor Diagnostic Agent

面向半导体工业设备性能数据的 Agent 化辅助诊断平台。系统围绕诊断案例组织数据、对话、工具调用、证据链、结论和报告，目标是帮助设备/工艺工程师分析性能异常并生成可审阅报告。

## Current Capabilities

- FastAPI 后端 API
- Vue/Vite 前端诊断案例工作区
- SQLite 元数据、会话、工具轨迹和 Artifact 存储
- 本地设备性能文件上传
- 可插拔诊断插件包骨架
- Stub LLM + Agent runtime + Tool Registry
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
4. Agent 依次调用解析、画像、趋势图、诊断工具。
5. WebUI 展示工具轨迹、Artifact、证据和报告草稿。

## Documentation

- [Requirements](REQUIREMENTS.md)
- [Architecture](docs/architecture.md)
- [Agent Design](docs/agent_design.md)
- [Service and Tool Contract](docs/service_tool_contract.md)
- [Development Guide](docs/dev_guide.md)
