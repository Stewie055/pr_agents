# LT Business Design

LT 是当前唯一设备族。不同型号通过插件 manifest/config 表达，不按型号复制插件。

## Logs

当前支持三类脱敏日志类型：

- `LT-D`: online production 生成日志，在线测校日志都在该文件中。
- `LT-C`: offline setup 测校日志。
- `LT-R`: offline setup 测校日志。

案例内维护日志文件池。用户可以上传多个日志文件，系统按文件名规则识别日志类型：

- 文件名包含 `LT-D` -> `log_kind=LT-D`, `scenario=online_production`
- 文件名包含 `LT-C` -> `log_kind=LT-C`, `scenario=offline_setup`
- 文件名包含 `LT-R` -> `log_kind=LT-R`, `scenario=offline_setup`

识别结果写入 `DatasetRecord` 的日志元数据字段，并在 case snapshot 中返回。

## Calibration Plugins

测校项很多，因此按测校项拆分插件。每个测校插件声明：

- 支持场景：offline setup / online production。
- 需要日志类型：LT-D / LT-C / LT-R。
- 支持型号。
- 业务描述。
- 被选中后可提供的工具。

Plugin 可以提供自己的 Service 和算法，但 Agent 只通过 Tool 调用。

## Agent Flow

```text
用户请求
  -> RouterAgent 判断意图
  -> PluginSelectorAgent 根据日志池和 plugin manifest 选择测校插件
  -> ToolScopeBuilder 构造 selected plugin tools + common tools
  -> ExecutorAgent 执行 ReAct
```

这种设计避免 tool explosion，同时允许每个测校项拥有独立算法。
