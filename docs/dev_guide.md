# Development Guide

## Backend

安装：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

`ppt_template_sdk` 已作为单文件 vendored 到仓库：

```text
src/semidiag/vendor/ppt_template_sdk.py
```

部署环境不需要访问私有 Git 仓库。该 SDK 依赖 `python-pptx`，如需升级 SDK，应从上游单文件版本替换该文件并跑完整测试。

运行：

```bash
semidiag-api
```

默认监听 `0.0.0.0:8000`。

本地默认 LLM 配置使用 DeepSeek V4 Flash。复制 `.env.example` 为 `.env`，填写 `SEMIDIAG_LLM_API_KEY` 后重启后端生效。生产运行时不再提供 stub provider；自动化测试使用测试专用 fake provider，不依赖真实模型和密钥。

测试：

```bash
python -m pytest
ruff check src tests
```

## Frontend

安装：

```bash
cd frontend
npm install
```

运行：

```bash
npm run dev
```

默认监听 `0.0.0.0:5173`。

测试和构建：

```bash
npm run typecheck
npm test
npm run build
```

完整本地质量门禁：

```bash
bash scripts/check.sh
```

## Adding A Diagnostic Package

1. 在 `business/services/` 中实现解析、清洗、指标画像、诊断、绘图和报告生成。
2. 在 `business/plugins/` 中注册测校项或分析插件，manifest 声明场景、日志类型、型号、描述和 tool names。
3. 在插件中声明 `tools=[ToolSpec(ToolDefinition(...), handler)]`，框架负责筛选插件并注册本轮可用工具。
4. 在 `business/plugins/<plugin_file_stem>/skills/*.md` 中编写可选 Skill，描述测校分析方法和报告要求。
5. 解析流程应输出结构化指标，Tool 负责写入 `MetricRepository`。
6. 绘图能力在 Service 中生成文件 Artifact，不在 Agent 或前端中重算业务图。
7. 报告能力优先使用 `ppt-template-sdk` 模板，占位符命名采用 `ph:<type>:<key>`。
8. 需要始终可用的公共能力放入 `business/tools/`。
9. 为 Service、Tool、Skill loader、API 和前端展示补充测试。

## Business Extensions

业务扩展文件放在仓库内 `business/`：

- `business/tools/*.py`: 公共业务工具，文件必须提供 `register(registry)`。
- `business/plugins/*.py`: LT 测校项插件，文件必须提供 `register(registry)`。
- `business/services/*.py`: 保密业务实现或非保密示例 Service，由 Tool/Plugin 调用，不直接被 Agent 调用。

服务启动时加载扩展。加载状态可通过 `GET /api/extensions` 查看，测校插件 manifest 可通过 `GET /api/calibrations` 查看。

详细规范见 `docs/extension_development.md` 和 `docs/lt_business_design.md`。

## Change Rules

- 每次新增功能必须补充自动化测试。
- 每次功能完成后必须执行对应测试。
- 每次修改设计或行为后必须更新 `README.md`、`REQUIREMENTS.md` 和 `docs/`。
- 产品化推进计划记录在 `plans/`，每个阶段或可独立验证的子阶段完成后单独提交 Git。

## Tasks

`InProcessTaskQueue` 是首版长任务基础设施，当前用于本地部署和测试。任务状态 API：

- `GET /api/tasks`
- `GET /api/tasks/{task_id}`

后续解析、绘图、PPT 和 Workflow 批处理应逐步迁移到该接口背后的任务抽象。

## Knowledge

本地知识库 API：

- `POST /api/knowledge`
- `GET /api/knowledge`
- `GET /api/knowledge?q=<keyword>`

当前实现是 SQLite 关键词检索，用于打通知识问答上下文；后续向量库/RAG adapter 应保持来源摘要语义。

## Workflow

Workflow API：

- `POST /api/cases/{case_id}/workflows`
- `GET /api/workflows`
- `POST /api/cases/{case_id}/workflows/{workflow_id}/run`

当前版本从成功的 Tool traces 生成模板，并支持在案例上手动重放。数据集类工具重放时自动使用当前案例最新数据集。
