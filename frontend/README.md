# Frontend Workspace

当前前端已经重建为 `React + Vite + TypeScript` 的诊断 Agent 工作台。

## 布局

- 左侧 `Chat Panel`
- 右侧 `Workbench`
- 右侧可折叠 `Debug Drawer`

## 接口

- `POST /api/v1/agent/sessions`
- `GET /api/v1/agent/sessions/{session_id}`
- `POST /api/v1/agent/sessions/{session_id}/messages`
- `GET /api/v1/agent/sessions/{session_id}/runs/{run_id}/stream`
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
