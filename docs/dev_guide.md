# Development Guide

## Backend

安装：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

运行：

```bash
semidiag-api
```

默认监听 `0.0.0.0:8000`。

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
4. 将需要暴露给 Agent 的能力注册为 Tool。
5. 为 Service、Tool、API 和前端展示补充测试。

## Change Rules

- 每次新增功能必须补充自动化测试。
- 每次功能完成后必须执行对应测试。
- 每次修改设计或行为后必须更新 `README.md`、`REQUIREMENTS.md` 和 `docs/`。
