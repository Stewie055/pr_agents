# LLM Provider

## Providers

当前支持：

- `stub`: 默认离线模式，不调用真实模型。
- `openai_compatible`: 调用 OpenAI-compatible `/v1/chat/completions`。

## Configuration

复制 `.env.example`：

```bash
cp .env.example .env
```

配置项：

```bash
SEMIDIAG_LLM_PROVIDER=openai_compatible
SEMIDIAG_LLM_BASE_URL=http://localhost:8001/v1
SEMIDIAG_LLM_MODEL=local-diagnostic-model
SEMIDIAG_LLM_API_KEY=change-me
SEMIDIAG_LLM_TIMEOUT=30
SEMIDIAG_LLM_TEMPERATURE=0.1
```

`.env.example` 默认使用 DeepSeek V4 Flash：

```bash
SEMIDIAG_LLM_PROVIDER=openai_compatible
SEMIDIAG_LLM_BASE_URL=https://api.deepseek.com
SEMIDIAG_LLM_MODEL=deepseek-v4-flash
SEMIDIAG_LLM_API_KEY=fill-your-deepseek-api-key
```

不想连接真实模型时，将 `SEMIDIAG_LLM_PROVIDER` 改为 `stub`，系统会使用 deterministic stub。

## Tool Calling

真实 LLM 使用 OpenAI tool calling：

- 第一阶段先由 LLM Router 输出 `RouteDecision` JSON。
- State Gate 通过后，分析/诊断/报告路径才进入 tool calling。
- 系统只暴露 `ToolRegistry` 中注册的白名单工具。
- `ToolDefinition.input_schema` 会转换为 OpenAI function parameters。
- LLM 返回未知工具、非法参数或非法 JSON 时，请求失败并写入审计。
- DeepSeek V4 thinking mode 的 tool-call 轮次会返回 `reasoning_content`；系统会在回传 tool result 给模型时保留该字段，避免 DeepSeek 返回 400。
- ReAct loop 的每一轮 tool-call 都会保留并回传 DeepSeek `reasoning_content`。

## Context Policy

发送给 LLM 的上下文只包含案例摘要、数据集元数据、Artifact 摘要、Evidence 摘要、最近消息和中期记忆。

不会发送原始 CSV 行级数据或完整设备文件内容。

## Failure Policy

真实 LLM 已启用时：

- Router 返回非法 JSON 时返回 API 错误。
- HTTP 4xx/5xx 返回 API 错误。
- 超时返回 API 错误。
- 非法 tool call 返回 API 错误。
- 不自动降级到 stub。

工具执行错误会作为 Observation 回传给 Agent，允许模型调整下一步；未知工具仍返回 API 错误。

只有未配置真实 LLM 时才使用 stub。

## Audit

LLM prompt、request 和 response 会完整记录到 `llm_audit_events`。

安全要求：

- 不记录 API key。
- 不记录 Authorization header 明文。
- 后续接入用户权限后，LLM audit 应纳入案例审计视图。

## Testing

自动化测试使用 `httpx.MockTransport` 模拟 OpenAI-compatible 服务，不依赖真实模型和密钥。
