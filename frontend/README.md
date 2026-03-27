# Frontend Workspace

当前前端实现为 `Vue + Vite` 的工业诊断 Agent 工作台。

## 组件职责

- `src/App.vue`
  - 只负责装配布局、注入 composable 状态和绑定组件事件。
- `src/composables/useAgentWorkspace.js`
  - WebUI 的主状态层。
  - 负责：
    - session 与消息请求
    - SSE 事件消费
    - process / artifacts / status bar / debug 数据映射
    - mock execution controls
- `src/composables/useDebugDrawerState.js`
  - 管理调试抽屉和各调试模块的展开状态，并写入本地存储。
- `src/components/chat/*`
  - 左侧 Chat Panel。
- `src/components/workbench/*`
  - 中间 Workbench。
- `src/components/debug/*`
  - 右侧 Debug Drawer 各个模块。
- `src/components/layout/*`
  - 页面壳、状态栏、抽屉布局。
- `src/mocks/workspaceDemoState.js`
  - 工作流节点、状态映射、推荐动作等 mock helper。

## 未来接真实 Agent 数据流的位置

- `useAgentWorkspace.js`
  - `handleEvent()`：
    当前把 SSE 事件映射到流程图、任务日志、工件和状态栏。接真实 agent 时优先改这里。
  - `hydrateTaskArtifacts(taskId)`：
    当前用 task detail + artifact content 补结果工件。接真实 chart/table/report 数据时优先改这里。
  - `pauseRun / resumeRun / rerunStep / modifyState`：
    当前是 mock 控制，后续接真实执行控制接口时替换这里。
- `workspaceDemoState.js`
  - 当前流程节点固定为四阶段。接真实多阶段 / 可重试流程图时替换这里的映射规则。

## 开发

```bash
pnpm install
pnpm build
```

如果本地环境具备浏览器运行条件，可选执行浏览器级回归：

```bash
pnpm test:browser:optional
```
