# Extension Development

业务扩展代码放在仓库内 `business/` 目录。真实保密实现可以离线开发后复制进来，服务重启时加载。

## Layout

```text
business/
  services/
    demo_csv_diagnostics.py
  tools/
    lt_log_pool_tool.py
  plugins/
    demo_csv_analysis.py
    lt_example_calibration.py
```

## Service Files

`business/services/*.py` 承载真实业务实现或非保密示例。Service 不直接暴露给 Agent，也不依赖 WebUI、Agent 或 LLM；它由 Tool/Plugin 调用，返回结构化 Artifact、Evidence 或业务数据。

## Tool Files

每个 `business/tools/*.py` 必须提供：

```python
def register(registry):
    registry.register(ToolDefinition(...), handler)
```

Tool 是 Agent 可调用的最小动作入口。handler 接收 `ToolContext` 和 `arguments`，返回 `ToolResult`。Tool 必须返回结构化 `ToolObservation`，不能只返回自然语言。

公共 Tool 会始终进入 common tool registry，例如日志池查看、知识检索、通用数据获取。平台默认 registry 不内置业务分析工具。

## Calibration Plugin Files

每个 `business/plugins/*.py` 必须提供：

```python
def register(registry):
    registry.register(CalibrationPlugin(manifest=..., build_tools=...))
```

Plugin 是测校项业务包和懒加载 Tool Provider。服务启动时只读取 manifest，插件被选中后才调用 `build_tools(context)` 构建 plugin tools。

Manifest 必须声明：

- `plugin_id`
- `display_name`
- `equipment_type`
- `scenarios`
- `log_kinds`
- `supported_models`
- `description`
- `tool_names`

Plugin tools 内部可以自由调用保密 Service、parser、cleaner、analyzer、plotter 和 reporter。平台只关心 ToolDefinition、ToolResult、Artifact、Evidence 和 Observation。
Manifest 的 `tool_names` 必须和 `build_tools(context)` 实际返回的工具一致，否则构建 active registry 时会报错，避免 Agent 看到不存在的能力。

## Loading Rules

- 服务启动时扫描 `business/tools/*.py` 和 `business/plugins/*.py`；`business/services/*.py` 由这些扩展文件按需导入。
- 文件必须有 callable `register(registry)`。
- 单个文件加载失败不会阻断服务启动。
- 加载状态通过 `GET /api/extensions` 查看。
- 测校插件 manifest 通过 `GET /api/calibrations` 查看。

## Tool Scope

Agent 不会看到所有插件的 tools。每轮分析流程为：

```text
Router -> PluginSelector -> ToolScopeBuilder -> ReAct Executor
```

本轮可用工具为：

```text
selected plugin tools + common tools
```

默认每轮最多选择 3 个插件，active tool registry 默认限制 12 个工具。
当工具数量超过限制时，优先保留被选中插件提供的业务工具，再补充 common tools。
