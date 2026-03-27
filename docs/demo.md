# Demo 说明

当前仓库提供两条适合外部展示的官方 Agent demo。推荐在 `llm` 模式下演示，`fake` 作为开发回退模式保留。

两条主线分别是：

- 文件主线：`A_DEMO` 文件数据 -> 科学绘图 -> 报告
- 数据库主线：清洗后数据库数据 -> 科学绘图 -> 报告

## 1. 安装依赖

```bash
uv sync --python 3.11
```

## 2. 以 llm 模式启动服务

设置环境变量后启动：

```bash
export PR_AGENTS_INTENT_MODE=llm
export PR_AGENTS_LLM_PROVIDER=glm
export PR_AGENTS_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export PR_AGENTS_LLM_MODEL="glm-4.5-air"
export PR_AGENTS_LLM_API_KEY="<your-api-key>"
uv run python -c "from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='0.0.0.0', port=8000)"
```

如果当前只是联调业务 `Service`，可改为：

```bash
export PR_AGENTS_INTENT_MODE=fake
```

## 3. 打开 WebUI

浏览器访问：

```text
http://<机器IP>:8000/
```

前端开发模式：

```text
http://<机器IP>:5173/
```

调试底层接口时再访问：

```text
http://<机器IP>:8000/docs
```

页面结构：

- 左侧 `Chat Panel`
- 右侧 `Workbench`
- 右侧 `Debug Drawer`

## 4. 主线一：文件 demo

推荐操作：

1. 在聊天区点击 `Run File Demo`
2. 观察右侧 `Workbench` 依次刷新：
   - `Run Overview`
   - `Tool Timeline`
   - `Metrics Table`
   - `Chart Preview`
   - `Report Preview`
3. 需要排查上下文时打开 `Debug Drawer`

等价 API 调用如下：

```bash
curl -s http://127.0.0.1:8000/api/v1/tasks/file-analysis \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "business_code": "A_DEMO",
  "objective": "Generate a scientific plot report for the demo dataset",
  "file_name": "demo_a.csv",
  "content": "temperature,pressure\n21.5,101.2\n22.1,101.5\n22.8,101.7\n",
  "source_profile": {
    "source_pattern": "per_business_file",
    "data_version": "demo-v1"
  },
  "chart_profile": {
    "chart_type": "scientific_plot"
  },
  "report_profile": {
    "template": "demo-template"
  }
}
JSON
```

## 5. 主线二：数据库 demo

推荐操作：

1. 在聊天区点击 `Run DB Demo`
2. 观察 `Workbench` 以相同结构刷新
3. 如需查看 prompt 和 memory，打开 `Debug Drawer`

等价 API 调用如下：

```bash
curl -s http://127.0.0.1:8000/api/v1/tasks/db-analysis \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "business_code": "A_DEMO",
  "objective": "Generate a scientific plot report from database data",
  "query_name": "demo_query",
  "sql": "select * from cleaned_demo_data",
  "source_profile": {
    "source_pattern": "per_business_file",
    "data_version": "demo-v1"
  },
  "chart_profile": {
    "chart_type": "scientific_plot"
  },
  "report_profile": {
    "template": "demo-template"
  }
}
JSON
```

## 6. 多轮追问

如果要演示 Agent 会话能力，可以先创建 session，再发送标准 prompt：

- `Please use A_DEMO file data to generate a scientific plot and report.`
- `Please use database data to generate a scientific plot and report for A_DEMO.`
- `Show me the report again.`
- `Please summarize the report key points.`

运行事件通过 `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream` 的 SSE 返回。

## 7. 排查

- 根路径没有交互界面
  先确认是否执行了 `cd frontend && pnpm build`，以及 FastAPI 是否读取到 `frontend/dist`。
- llm 模式响应慢
  当前会先看到聊天区轻量状态，再在 `Workbench` 中逐步刷新运行产物。
- 模型不可用
  可切换到 `fake` 模式，先保证 demo 和业务适配流程跑通。
