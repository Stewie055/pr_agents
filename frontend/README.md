# Frontend Workspace

前端是 `React + Vite + TypeScript` 科研实验室风格数据分析工作台。

## 布局

- 左侧 `Source Panel`：CSV 上传、SQL 注册、source 选择、模型模式切换、取消任务
- 中间 `Chat Panel`：对话、prompt、Agent 工具状态
- 右侧 `Workbench`：run 概览、工具时间线、metrics、图表图片、报告
- `Debug Drawer`：prompt、memory、run metadata 和 tool calls

## 接口

- `POST /api/v1/agent/sessions`
- `POST /api/v1/agent/sessions/{session_id}/sources/csv-upload`
- `POST /api/v1/agent/sessions/{session_id}/sources/database`
- `POST /api/v1/agent/sessions/{session_id}/messages`
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/content`
- `GET /api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/raw`

## 本地开发

```bash
cd frontend
pnpm install
pnpm dev --host 0.0.0.0 --port 5173 --strictPort
```

## 测试

```bash
cd frontend
pnpm test
pnpm build
```
