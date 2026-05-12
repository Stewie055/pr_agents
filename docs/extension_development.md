# Extension Development

业务扩展代码放在仓库内 `business/` 目录。真实保密实现可以离线开发后复制进来，服务重启时加载。

## Layout

```text
business/
  tools/
    lt_log_pool_tool.py
  plugins/
    lt_example_calibration.py
```

## Tool Files

每个 `business/tools/*.py` 必须提供：

```python
def register(registry):
    registry.register(ToolDefinition(...), handler)
```

Tool 是 Agent 可调用的最小动作入口。handler 接收 `ToolContext` 和 `arguments`，返回 `ToolResult`。Tool 必须返回结构化 `ToolObservation`，不能只返回自然语言。

公共 Tool 会始终进入 common tool registry，例如日志池查看、知识检索、通用数据获取。

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

## Loading Rules

- 服务启动时扫描 `business/tools/*.py` 和 `business/plugins/*.py`。
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
common tools + selected plugin tools
```

默认每轮最多选择 3 个插件，active tool registry 默认限制 12 个工具。
