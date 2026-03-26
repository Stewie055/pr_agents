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

页面中有两条官方入口：

- `Run File Demo`
- `Run DB Demo`

## 4. 主线一：文件 demo

推荐操作：

1. 点击 `Run File Demo`
2. 等待 Agent 返回最终回复
3. 展开 `Task details`
4. 查看 `Report preview`

等价 prompt：

```text
Please use A_DEMO file data to generate a scientific plot and report.
```

预期结果：

- assistant 最终回复包含 `Completed file analysis for A_DEMO`
- `Task details` 中包含两步：
  - `Run file analysis workflow for A_DEMO`
  - `Summarize workflow results for the user`
- `Report preview` 中包含：
  - `business_code=A_DEMO`
  - 请求 objective
  - `Analysis completed`

## 5. 主线二：数据库 demo

推荐操作：

1. 点击 `Run DB Demo`
2. 等待 Agent 返回最终回复
3. 展开 `Task details`
4. 查看数据库主线的步骤和报告预览

等价 prompt：

```text
Please use database data to generate a scientific plot and report for A_DEMO.
```

预期结果：

- assistant 最终回复包含 `Completed database analysis for A_DEMO`
- `Task details` 中第一步为：
  - `Run database analysis workflow for A_DEMO`
- 当前 stub 查询会使用固定数据库入口语义：
  - `query_name = demo_query`
  - `sql = select * from cleaned_demo_data`

## 6. 多轮追问

完成任一主线后，可以继续追问两类标准问题。

查看完整报告：

```text
Show me the report again.
```

查看摘要重点：

```text
Please summarize the report key points.
```

预期结果：

- `Show me the report again.` 返回完整报告文本
- `Please summarize the report key points.` 返回摘要文本，并在 metadata 中保留 `report_preview`

## 7. API 调试路径

如果需要调试底层接口，可直接调用同步任务 API。

文件分析：

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

数据库分析：

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

## 8. 排查

- 普通聊天没有执行任务
  这是正常行为。只有明确分析请求才会进入 plan 和 workflow。
- 看不到完整报告正文
  展开 assistant 回复下方的 `Task details`，或继续发送 `Show me the report again.`
- llm 模式响应慢
  当前会通过 `SSE` 先显示 `Queued / Routing / Planning`；明显任务还会优先走 fast-path。
- 模型不可用
  可切换到 `fake` 模式，先保证 demo 和业务适配流程跑通。
