# Demo 说明

当前仓库提供两条适合外部展示的官方 Agent demo。第一阶段正式采用 `ReAct` 单 Agent 模式，demo 通过显式 `demo source` 进入系统。

三条主线分别是：

- CSV 上传主线：上传 CSV -> 选择 source -> 后台分析 -> 图表/表格/报告
- 文件 demo 主线：注册 `a_demo_file` -> 后台分析 -> 图表/表格/报告
- 数据库主线：注册 SQL source 或 `a_demo_db` -> 后台分析 -> 图表/表格/报告

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

## 4. CSV 上传 demo

前端操作：

1. 在左侧上传 CSV 文件。
2. 选择刚上传的 source。
3. 输入：`分析当前数据源，生成结构化报告和图表。`
4. 观察 SSE 推送的任务状态，以及右侧图表、表格和报告。

等价 API：

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions | jq -r '.session_id')
SOURCE_ID=$(curl -s -X POST \
  -F "file=@examples/demo_a.csv" \
  -F "business_code=file_analysis" \
  http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/sources/csv-upload | jq -r '.source.source_id')
START=$(curl -s http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -d "{\"content\":\"分析当前数据源，生成结构化报告和图表。\",\"source_id\":\"$SOURCE_ID\",\"model_mode\":\"fake\"}")
echo "$START"
```

## 5. 文件 demo

前端操作：

1. 点击 `Run File Demo`
2. 前端先注册 `a_demo_file`
3. 再发送标准 prompt
4. 观察 `Workbench` 中的 Run Overview、Tool Timeline、Metrics、Chart、Report

等价 API：

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions | jq -r '.session_id')
SOURCE_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/demo-sources/a_demo_file | jq -r '.source_id')
curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -d "{\"content\":\"Please use the selected file source to generate a structured report and chart.\",\"source_id\":\"$SOURCE_ID\"}"
```

## 6. 数据库 demo

前端操作：

1. 点击 `Run DB Demo`
2. 前端先注册 `a_demo_db`
3. 再发送标准 prompt

等价 API：

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions | jq -r '.session_id')
SOURCE_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/demo-sources/a_demo_db | jq -r '.source_id')
curl -s -X POST http://127.0.0.1:8000/api/v1/agent/sessions/$SESSION_ID/messages \
  -H 'Content-Type: application/json' \
  -d "{\"content\":\"Please analyze the selected SQL source and generate a structured report.\",\"source_id\":\"$SOURCE_ID\"}"
```

## 7. 多轮追问

在同一 session 下继续发送：

- `Show me the report again.`
- `Please summarize the report key points.`

运行事件通过 `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream` 的 SSE 返回。

## 8. 排查

- 分析请求没有执行
  先确认当前 session 是否已显式选择 source。
- 任务没有停止
  running 任务只在 step 边界响应取消；queued 任务会直接变为 cancelled。
- llm 模式失败
  当前会在同一 run 内回退到 `fake`，`Debug Drawer` 和 run metadata 可见 `used_fallback`。
- 根路径没有交互界面
  先确认是否执行了 `cd frontend && pnpm build`。
