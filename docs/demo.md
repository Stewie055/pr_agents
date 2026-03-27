# Demo 说明

当前仓库提供一套面向“工业数据分析 / 诊断”的 Agent 工作台 demo。推荐在 `llm` 模式下演示，`fake` 作为开发回退模式保留。

新版 WebUI 采用诊断工作台布局：

- 左侧 `Chat Panel`
  - Project / 当前任务
  - Input Query 摘要
  - 聊天消息流
  - 输入框与文件上传入口
- 中间 `Workbench`
  - `Flow Graph`
  - `Current Step`
  - `Task Log`
  - `Fault Analysis Chart`
  - `Diagnosis Summary`
  - `Recommended Actions`
  - `Report Preview`
- 右侧 `Debug Drawer`
  - 默认收起
  - 支持查看工具调用、prompt 摘要、memory 状态和 execution controls
- 底部 `Global Status Bar`
  - 展示当前步骤、当前工具、运行状态和耗时
  - `Pause / Resume` 可直接切换运行状态
  - `Rerun Step` 会重新拉起一轮流式执行

官方 demo 仍保留两条主线：

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

页面中有两条官方入口，适合直接演示：

- `Run File Demo`
- `Run DB Demo`

左侧聊天区只同步轻量回复；图表、诊断摘要、建议措施和报告预览会在中间 `Workbench` 中逐步刷新。

## 4. 主线一：文件 demo

推荐操作：

1. 点击 `Run File Demo`
2. 观察 `Workbench` 中的 `Flow Graph`、`Current Step` 和 `Task Log`
3. 等待 `Fault Analysis Chart`、`Diagnosis Summary`、`Recommended Actions` 和 `Report Preview` 逐步出现
4. 如需调试，再展开右侧 `Debug Drawer`

等价 prompt：

```text
Please use A_DEMO file data to generate a scientific plot and report.
```

预期结果：

- 聊天区 assistant 最终回复包含 `Completed file analysis for A_DEMO`
- `Workbench` 中：
  - `Flow Graph` 按 `Load Data -> Analyze Metrics -> Identify Issues -> Generate Report` 推进
  - `Current Step` 和 `Task Log` 持续更新
  - `Diagnosis Summary` 显示结构化摘要
  - `Recommended Actions` 按 `High / Medium / Low` 展示建议
  - `Report Preview` 中包含 `business_code=A_DEMO`、请求 objective 和 `Analysis completed`

## 5. 主线二：数据库 demo

推荐操作：

1. 点击 `Run DB Demo`
2. 观察 `Workbench` 中过程区与结果区的刷新
3. 查看数据库主线的 `Task Log` 和 `Report Preview`
4. 如需查看底层运行细节，再展开 `Debug Drawer`

等价 prompt：

```text
Please use database data to generate a scientific plot and report for A_DEMO.
```

预期结果：

- assistant 最终回复包含 `Completed database analysis for A_DEMO`
- `Workbench` 中第一阶段会体现数据库入口语义
- 当前 stub 查询使用固定数据库入口语义：
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
- `Please summarize the report key points.` 返回摘要文本
- 聊天区继续保持简洁；报告相关工件仍主要展示在 `Workbench`

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

## 8. 工作台观察点

- 聊天区只显示简洁的状态同步和最终回复，不堆完整图表和报告
- `Workbench` 是视觉中心，过程区和结果区会随着 agent 执行逐步刷新
- `Debug Drawer` 默认收起，对普通演示弱化存在感；需要调试时再展开
- `Global Status Bar` 始终可见，用于观察当前步骤、工具、状态和耗时

## 9. 排查

- 普通聊天没有执行任务
  这是正常行为。只有明确分析请求才会进入 plan 和 workflow。
- 看不到完整报告正文
  继续发送 `Show me the report again.`，或查看 `Workbench` 中的 `Report Preview`
- llm 模式响应慢
  当前会通过 `SSE` 先刷新 `Workbench` 的过程区和底部状态栏。
- 模型不可用
  可切换到 `fake` 模式，先保证 demo 和业务适配流程跑通。
