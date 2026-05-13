# Extension Development

业务扩展代码放在仓库内 `business/` 目录。真实保密实现可以离线开发后复制进来，服务重启时加载。

## Layout

```text
business/
  services/
    csv_file_analysis.py
  tools/
    lt_log_pool_tool.py
  plugins/
    csv_file_analysis/
      plugin.json
      plugin.py
    lt_example_calibration/
      plugin.json
      plugin.py
      skills/
        offline_check.md
  file_classifiers/
    lt_log_metadata.py
```

## Service Files

`business/services/*.py` 承载真实业务实现或非保密示例。Service 不直接暴露给 Agent，也不依赖 WebUI、Agent 或 LLM；它由 Tool/Plugin 调用，返回结构化 Artifact、Evidence 或业务数据。

## Tool Files

每个 `business/tools/*.py` 必须提供：

```python
def register(registry):
    registry.register(ToolDefinition(...), handler)
```

Tool 是 Agent 可调用的最小动作入口。handler 接收 `ToolContext` 和 `arguments`，返回 `ToolResult`。`ToolResult` 就是回填给 ReAct loop 的结构化 observation payload，不能只返回自然语言。

公共 Tool 会始终进入 common tool registry，例如日志池查看、知识检索、通用数据获取。平台默认 registry 不内置业务分析工具。

## Calibration Plugin Files

每个业务插件是一个目录：

```text
business/plugins/<plugin_name>/
  plugin.json
  plugin.py
  skills/*.md
```

Plugin 是测校项业务包。`plugin.json` 负责 manifest-only discovery，不执行业务代码即可发现插件信息、工具名、Skill 名和配置需求。`plugin.py` 只导出 `TOOLS = [ToolSpec(...)]`，提供工具实现。业务开发者不需要实现 `build_tools`，也不需要在 Python 中重复写插件 manifest。

Manifest 必须声明：

- `plugin_id`
- `display_name`
- `equipment_type`
- `scenarios`
- `log_kinds`
- `supported_models`
- `description`
- `tools`
- `skills`
- `capability_tags`
- `requires_config`

Plugin tools 内部可以自由调用保密 Service、parser、cleaner、analyzer、plotter 和 reporter。平台只关心 ToolDefinition、ToolResult、Artifact 和 Evidence。
`tools` 和 `skills` 当前可以写字符串数组。框架会把它们归一为 `tool_names` 和 `skill_names`。`requires_config` 用于声明业务插件运行前需要的环境变量或配置项；缺失时插件状态为 `degraded`，不会进入 Agent active tool registry。

`plugin.json` 示例：

```json
{
  "plugin_id": "lt.example.measurement",
  "display_name": "LT Example Measurement",
  "equipment_type": "LT",
  "scenarios": ["offline_setup"],
  "log_kinds": ["LT-C"],
  "supported_models": ["*"],
  "description": "Example LT measurement analysis plugin.",
  "capability_tags": ["lt", "measurement"],
  "requires_config": [],
  "tools": ["lt_example_measurement_analyze"],
  "skills": ["lt_example_measurement"]
}
```

`plugin.py` 示例：

```python
from semidiag.tools import ToolContext, ToolDefinition, ToolResult, ToolSpec


def analyze(context: ToolContext, arguments: dict) -> ToolResult:
    dataset = context.active_dataset
    if dataset is None:
        raise ValueError("This tool requires an active dataset.")
    return ToolResult(
        summary="Analysis completed.",
        data={"filename": dataset.filename},
        next_suggestions=[],
    )


TOOLS = [
    ToolSpec(
        definition=ToolDefinition(
            name="lt_example_measurement_analyze",
            description="Analyze the current LT measurement log.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
            origin="business:lt.example.measurement",
            phase="analyze",
            capability_tags=["lt", "measurement"],
        ),
        handler=analyze,
    )
]
```

## ToolContext

所有 Tool 统一接收 `ToolContext`：

- `case_id`: 当前诊断案例 ID，仅用于后端校验和落库，不应展示给用户。
- `actor`: 当前调用者。
- `repository`: 元数据仓储，可读取/保存 Artifact、Evidence、Trace、消息等。
- `case`: 当前 `DiagnosticCase`，可能为空。
- `datasets`: 当前案例全部数据集元数据。
- `active_dataset`: 本轮自动选中的当前数据集。工具应优先使用它，而不是要求用户或 LLM 传 dataset id。
- `metric_repository`: 结构化指标仓储，当前 SQLite，后续可换 ClickHouse adapter。
- `generated_root`: 图表、报告等生成文件根目录。

业务 Tool 必须校验数据归属当前案例。需要系统注入的参数应放到 `ToolDefinition.system_injected_args`，不要暴露给 LLM 或用户。

## Plugin Skills

Skill 是插件附带的业务指导文档，不执行代码。它用于告诉 Agent 某个测校如何分析、先看什么证据、报告怎么组织。Skill 只有在对应插件被 PluginSelector 选中后才进入 ReAct prompt，避免所有测校知识同时污染上下文。

Skill 文件放在：

```text
business/plugins/<plugin_name>/skills/*.md
```

Markdown 必须使用 frontmatter：

```markdown
---
name: lt_example_offline_check
description: Guidance for LT offline setup check.
plugin_id: lt.example.offline_check
triggers: [offline, LT-C, LT-R]
max_context_chars: 4000
---

# Analysis Guidance

这里写测校分析方法、判断准则、报告要求和注意事项。
```

字段说明：

- `name`: Skill 唯一名，进入插件 manifest 的 `skill_names`。
- `description`: 给调试台、API 和 Agent 的简短说明。
- `plugin_id`: 必须匹配已注册插件，否则加载为 error。
- `triggers`: 可选关键词，后续用于更细粒度 skill selection。
- `max_context_chars`: 可选，单个 Skill 注入 prompt 的最大字符数，默认 4000。

Skill 加载失败不会阻断服务启动，错误会出现在 `GET /api/extensions`。

## ToolResult

Tool handler 返回：

- `summary`: 简短结果摘要，供用户进度和 LLM observation 使用。
- `data`: 结构化结果，写字段、统计、诊断结论、报告章节等，不放完整原始文件内容。
- `artifacts`: 新产生的 Artifact 对象，Registry 会统一落库。
- `evidence`: 新产生的 Evidence 对象，Registry 会统一落库。
- `artifact_ids` / `evidence_ids`: 已有或新产生对象的引用。
- `task_ids`: 异步任务引用，适用于绘图、PPT 报告和长耗时分析。
- `next_suggestions`: 失败恢复或下一步候选工具名，仅作为 LLM 提示，不是强制流程。

`ToolResult` 和 observation 不再拆成两个重复结构；Runtime 会直接把 ToolResult 转成统一 observation 字典回填模型。

## Tool Guardrails

框架在每次 Tool 调用前后执行默认 guardrail：

- `active_dataset` 必须属于当前 case。
- `dataset_id` 只能由系统通过 `system_injected_args` 注入，不能由 LLM 或用户手填。
- ToolResult.summary 不能为空。
- ToolResult 必须包含结构化 `data`、Artifact、Evidence 或已存在对象引用。
- `risk_level=high` 的工具仍会进入人工审批拦截。

Guardrail 失败会写入 ToolCallTrace error，并作为 error observation 回填给模型。

## Async Tool Tasks

长耗时 Tool 应提交任务而不是阻塞请求线程。任务型 Tool 返回 `ToolResult(task_ids=[...], data={"task_id": ..., "task_status": ...})`，后台任务完成后自行写入 Artifact/Evidence，并把生成的 `artifact_ids`/`evidence_ids` 放进任务结果，方便前端刷新产物。

当前通用 CSV 插件已将 `build_trend_chart` 和 `generate_report` 改为任务型工具。任务状态 API：

- `GET /api/tasks`
- `GET /api/tasks?case_id=<case_id>`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/cancel`

任务记录持久化到 SQLite。服务重启时，未完成的 `pending/running` 任务会被标记为 `interrupted`，插件应允许用户重新触发对应分析或报告生成。

## File Classifiers

文件类型识别放在 `business/file_classifiers/`，例如 `lt_log_metadata.py`。LT 日志的 `log_kind` 和 `scenario` 当前由 `detect_file_metadata(filename, content_type, content_preview)` 返回；真实业务可根据文件名后缀、内容头、魔数或日志片段扩展该函数。

## Loading Rules

- 服务启动时扫描 `business/tools/*.py` 和 `business/plugins/*/plugin.json`；`business/services/*.py` 由这些扩展文件按需导入。
- Common tool 文件必须有 callable `register(registry)`；插件实现文件必须导出 `TOOLS: list[ToolSpec]`。
- 单个扩展加载失败不会阻断服务启动。
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
