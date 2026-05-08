from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from semidiag.agent.llm import StubLLMProvider
from semidiag.agent.memory import MemoryService
from semidiag.domain import AgentMessage, AnalysisArtifact, ToolCallTrace
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import GenericEquipmentPlugin
from semidiag.tools import ToolContext, ToolRegistry, build_default_registry


@dataclass
class AgentTurnResult:
    message: AgentMessage
    artifacts: list[AnalysisArtifact]
    tool_traces: list[ToolCallTrace]
    summary: str


class AgentRuntime:
    def __init__(
        self,
        repository: SQLiteRepository,
        registry: ToolRegistry | None = None,
        llm: StubLLMProvider | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or build_default_registry()
        self.llm = llm or StubLLMProvider()
        self.memory = memory or MemoryService()
        self.plugin = GenericEquipmentPlugin()

    def handle_user_message(
        self,
        *,
        case_id: str,
        content: str,
        dataset_id: str | None = None,
        actor: str = "engineer",
    ) -> AgentTurnResult:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        self.repository.add_message(AgentMessage(case_id=case_id, role="user", content=content))

        datasets = self.repository.list_case_datasets(case_id)
        active_dataset_id = dataset_id or (datasets[-1].id if datasets else None)
        tool_names = self.llm.plan_tools(content, has_dataset=active_dataset_id is not None)

        context = ToolContext(
            case_id=case_id,
            actor=actor,
            repository=self.repository,
            plugin=self.plugin,
        )
        summaries: list[str] = []
        for name in tool_names:
            arguments: dict[str, Any] = {}
            if name in {"parse_dataset", "profile_dataset", "build_trend_chart"}:
                arguments["dataset_id"] = active_dataset_id
            result = self.registry.run(name, context, arguments)
            summaries.append(f"{name}: {result.summary}")

        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)
        if summaries:
            content_out = (
                "已完成设备性能辅助诊断。请在证据链和报告草稿基础上进行工程师确认。\n"
                + "\n".join(f"- {summary}" for summary in summaries)
            )
        else:
            content_out = "请先上传设备性能数据文件，之后我可以执行解析、画像、趋势和辅助诊断。"

        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=content_out,
                metadata={"tool_count": len(tool_names), "artifact_count": len(artifacts)},
            )
        )
        self.memory.update_midterm(case_id, content_out[:500])
        return AgentTurnResult(
            message=assistant_message,
            artifacts=artifacts,
            tool_traces=tool_traces,
            summary=content_out,
        )
