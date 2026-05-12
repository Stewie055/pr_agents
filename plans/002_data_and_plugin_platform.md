# Phase 2: Data And Plugin Platform

## Goal

把 generic CSV demo 演进为真实业务可接入的插件平台和指标数据底座。

## Key Work

- 定义插件包结构：parser、metric schema、rules/models、chart renderers、report renderers、tool exposure。
- 增加插件注册表，支持按 `equipment_type` 选择业务插件。当前基础注册表和 `/api/plugins` 已完成。
- 增加结构化指标模型和仓储接口，默认 SQLite/本地实现可运行，ClickHouse 作为目标适配。
- Tool 层只做 schema、审计、Observation 和 Service 调用，不承载业务算法。
- 报告模板从运行时默认模板升级为插件可提供模板和 renderer。

## Acceptance

- Generic plugin 作为完整示例插件存在。
- CSV demo 可通过插件注册表运行。
- 指标写入接口有自动化测试。
- Service/Tool contract 文档更新。
