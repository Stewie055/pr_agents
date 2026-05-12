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

本地默认 LLM 配置使用 DeepSeek V4 Flash。复制 `.env.example` 为 `.env`，填写 `SEMIDIAG_LLM_API_KEY` 后重启后端生效。若暂不使用真实模型，将 `SEMIDIAG_LLM_PROVIDER` 改为 `stub`。

测试：

```bash
python -m pytest
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
npm test
npm run build
```

## Adding A Diagnostic Package

1. 新建插件类并继承 `DiagnosticPlugin`。
2. 提供设备类型、展示名称和业务 Service。
3. 在 Service 中实现解析、指标画像、诊断和报告。
4. 绘图能力在 Service 中生成文件 Artifact，不在 Agent 或前端中重算业务图。
5. 报告能力优先使用 `ppt-template-sdk` 模板，占位符命名采用 `ph:<type>:<key>`。
6. 将需要暴露给 Agent 的能力注册为 Tool。
7. 为 Service、Tool、API 和前端展示补充测试。

## Change Rules

- 每次新增功能必须补充自动化测试。
- 每次功能完成后必须执行对应测试。
- 每次修改设计或行为后必须更新 `README.md`、`REQUIREMENTS.md` 和 `docs/`。
- 产品化推进计划记录在 `plans/`，每个阶段或可独立验证的子阶段完成后单独提交 Git。
