# Demo 说明

当前仓库提供两条适合外部展示的官方 Agent demo。第一阶段正式采用 `ReAct` 单 Agent 模式，demo 通过显式 `demo source` 进入系统。

两条主线分别是：

- 文件主线：注册 `a_demo_file` -> 科学绘图 -> 报告
- 数据库主线：注册 `a_demo_db` -> 科学绘图 -> 报告

## 1. 安装依赖

```bash
uv sync --python 3.11
cd frontend && pnpm install
```

## 2. 启动服务

`llm` 模式：

```bash
export PR_AGENTS_INTENT_MODE=llm
export PR_AGENTS_LLM_PROVIDER=glm
export PR_AGENTS_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export PR_AGENTS_LLM_MODEL="glm-4.5-air"
export PR_AGENTS_LLM_API_KEY="<your-api-key>"
uv run python -c "from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='0.0.0.0', port=8000)"
```

开发与回归场景可切到：

```bash
export PR_AGENTS_INTENT_MODE=fake
```

## 3. 打开 WebUI

- `http://<机器IP>:8000/`
- `http://<机器IP>:5173/`
- `http://<机器IP>:8000/docs`

## 4. 文件 demo

前端操作：

1. 点击 `Run File Demo`
2. 前端先注册 `a_demo_file`
3. 再发送标准 prompt
4. 观察 `Workbench` 中的 Run Overview、Tool Timeline、Metrics、Chart、Report

等价 API：

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions | jq -r '.session_id')
SOURCE_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/demo-sources/a_demo_file | jq -r '.source_id')
curl -s http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -d "{\"content\":\"Please use A_DEMO file data to generate a scientific plot and report.\",\"source_id\":\"$SOURCE_ID\"}"
```

## 5. 数据库 demo

前端操作：

1. 点击 `Run DB Demo`
2. 前端先注册 `a_demo_db`
3. 再发送标准 prompt

等价 API：

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions | jq -r '.session_id')
SOURCE_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/demo-sources/a_demo_db | jq -r '.source_id')
curl -s http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -d "{\"content\":\"Please use database data to generate a scientific plot and report for A_DEMO.\",\"source_id\":\"$SOURCE_ID\"}"
```

## 6. 多轮追问

在同一 session 下继续发送：

- `Show me the report again.`
- `Please summarize the report key points.`

运行事件通过 `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream` 的 SSE 返回。

## 7. 排查

- 分析请求没有执行
  先确认当前 session 是否已注册匹配 source。
- llm 模式失败
  当前会在同一 run 内回退到 `fake`，`Debug Drawer` 和 run metadata 可见 `used_fallback`。
- 根路径没有交互界面
  先确认是否执行了 `cd frontend && pnpm build`。
