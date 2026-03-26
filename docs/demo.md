# Demo 说明

本仓库内置一条可直接演示的官方 demo，目标是跑通：

- A 类文件业务
- `business_code=A_DEMO`
- 文件入口
- `scientific_plot` 图表
- 报告生成与读取
- 聊天式 Agent WebUI

## 1. 安装依赖

```bash
uv sync --python 3.11
```

## 2. 启动服务

```bash
uv run python -c "from pr_agents.bootstrap import build_api_app; import uvicorn; uvicorn.run(build_api_app(), host='0.0.0.0', port=8000)"
```

## 3. 打开 WebUI

浏览器访问：

```text
http://<机器IP>:8000/
```

页面操作：

1. 在左侧查看或创建会话
2. 点击 `Run A_DEMO`
3. 在右侧消息流中查看 Agent 回复
4. 展开执行卡片查看计划和工具调用
5. 在底部输入框继续输入 “Show me the report again.” 做多轮追问

## 4. API 方式发送 demo 请求

如果需要调试底层接口，再使用以下命令：

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

预期返回关键字段：

- `status = succeeded`
- `result.chart.chart_type = scientific_plot`
- `result.report` 非空
- `task_id` 可用于后续查询

## 5. 查询任务详情

将上一步返回的 `task_id` 代入：

```bash
curl -s http://127.0.0.1:8000/api/v1/tasks/<task_id>
```

预期结果：

- `task.status = succeeded`
- `artifacts` 中包含 `dataset`、`chart`、`report`
- `task.input_summary.business_code = A_DEMO`

## 6. 读取报告内容

从任务详情的 `artifacts` 中找到 `report` 对应的 `artifact_id`，然后执行：

```bash
curl -s http://127.0.0.1:8000/api/v1/artifacts/<artifact_id>/content
```

预期报告内容至少包含：

- `business_code=A_DEMO`
- 请求中的 `objective`
- `Analysis completed`

## 7. 排查

- 返回 `404`
  检查 `task_id` 或 `artifact_id` 是否来自同一次请求
- 返回 `415`
  说明读取的不是文本 artifact，应改为读取 `report` 而不是图表二进制产物
- 启动失败
  检查是否已执行 `uv sync --python 3.11`
