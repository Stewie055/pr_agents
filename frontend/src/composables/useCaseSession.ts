import { computed, ref } from "vue";
import {
  createCase,
  exportCaseTrace,
  getCase,
  getCaseTrace,
  streamMessage,
  uploadDataset,
  type AgentMessage,
  type CaseSnapshot,
  type CaseTrace,
  type StreamEvent
} from "../api";

export type ProgressItem = {
  id: string;
  label: string;
  status: "running" | "done" | "error";
  detail?: string;
};

export function useCaseSession() {
  const caseTitle = ref("设备性能异常诊断案例");
  const draftMessage = ref("请分析这份设备性能数据，给出诊断、证据和建议。");
  const loading = ref(false);
  const uploadLoading = ref(false);
  const reportLoading = ref(false);
  const traceLoading = ref(false);
  const error = ref("");
  const snapshot = ref<CaseSnapshot | null>(null);
  const trace = ref<CaseTrace | null>(null);
  const debugMode = ref(new URLSearchParams(window.location.search).get("debug") === "trace");
  const transientMessages = ref<AgentMessage[]>([]);
  const progressItems = ref<ProgressItem[]>([]);

  const activeDatasetId = computed(() => snapshot.value?.datasets.at(-1)?.id);
  const latestDatasetName = computed(() => snapshot.value?.datasets.at(-1)?.filename);
  const hasDataset = computed(() => Boolean(activeDatasetId.value));
  const displayMessages = computed(() => [...(snapshot.value?.messages ?? []), ...transientMessages.value]);
  const caseStateText = computed(() => {
    if (!snapshot.value) {
      return "尚未创建案例";
    }
    if (hasDataset.value) {
      return `数据已就绪：${latestDatasetName.value}`;
    }
    return "等待上传设备性能 CSV";
  });

  async function ensureCase() {
    if (snapshot.value) {
      return snapshot.value.case.id;
    }
    const diagnosticCase = await createCase(caseTitle.value);
    snapshot.value = await getCase(diagnosticCase.id);
    return diagnosticCase.id;
  }

  async function createNewCase() {
    loading.value = true;
    error.value = "";
    try {
      const diagnosticCase = await createCase(caseTitle.value);
      snapshot.value = await getCase(diagnosticCase.id);
      transientMessages.value = [];
      progressItems.value = [];
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建案例失败";
    } finally {
      loading.value = false;
    }
  }

  async function uploadFile(file: File) {
    uploadLoading.value = true;
    error.value = "";
    try {
      const caseId = await ensureCase();
      await uploadDataset(caseId, file);
      snapshot.value = await getCase(caseId);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "上传失败";
    } finally {
      uploadLoading.value = false;
    }
  }

  async function sendCurrentMessage(content = draftMessage.value) {
    if (!content.trim()) {
      return;
    }
    loading.value = true;
    error.value = "";
    progressItems.value = [];
    const caseId = await ensureCase();
    const assistantMessage: AgentMessage = {
      id: "streaming_assistant",
      role: "assistant",
      content: ""
    };
    transientMessages.value = [
      { id: "streaming_user", role: "user", content },
      assistantMessage
    ];

    try {
      await streamMessage(caseId, content, activeDatasetId.value, (event) => handleStreamEvent(event, assistantMessage));
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Agent 调用失败";
      markLastProgressError(error.value);
    } finally {
      loading.value = false;
    }
  }

  async function generateReport() {
    reportLoading.value = true;
    try {
      await sendCurrentMessage("请基于当前分析结果生成诊断 PPT 报告。");
    } finally {
      reportLoading.value = false;
    }
  }

  function handleStreamEvent(event: StreamEvent, assistantMessage: AgentMessage) {
    if (event.event === "started") {
      addProgress("请求已提交", "running", event.data.message);
      return;
    }
    if (event.event === "route") {
      completeRunning();
      addProgress(`意图识别：${event.data.intent}`, "done", event.data.user_goal || event.data.reason);
      return;
    }
    if (event.event === "tool_start") {
      completeRunning();
      addProgress(`执行工具：${event.data.tool_name}`, "running");
      return;
    }
    if (event.event === "tool_result") {
      completeRunning(event.data.error ? "error" : "done", event.data.summary);
      return;
    }
    if (event.event === "artifact_created") {
      addProgress(`产物生成：${event.data.artifact.title}`, "done", event.data.artifact.kind);
      return;
    }
    if (event.event === "message_delta") {
      assistantMessage.content += event.data.delta;
      return;
    }
    if (event.event === "final") {
      completeRunning("done");
      snapshot.value = {
        ...(snapshot.value as CaseSnapshot),
        messages: [...((snapshot.value as CaseSnapshot).messages ?? []), event.data.message],
        artifacts: event.data.artifacts,
        tool_traces: event.data.tool_traces
      };
      getCase((snapshot.value as CaseSnapshot).case.id).then((fresh) => {
        snapshot.value = fresh;
        transientMessages.value = [];
      });
      trace.value = null;
      return;
    }
    if (event.event === "error") {
      error.value = event.data.detail;
      markLastProgressError(event.data.detail);
    }
  }

  function addProgress(label: string, status: ProgressItem["status"], detail?: string) {
    progressItems.value.push({
      id: `${Date.now()}_${progressItems.value.length}`,
      label,
      status,
      detail
    });
  }

  function completeRunning(status: ProgressItem["status"] = "done", detail?: string) {
    const item = [...progressItems.value].reverse().find((candidate) => candidate.status === "running");
    if (item) {
      item.status = status;
      item.detail = detail || item.detail;
    }
  }

  function markLastProgressError(detail: string) {
    completeRunning("error", detail);
    if (!progressItems.value.length) {
      addProgress("请求失败", "error", detail);
    }
  }

  async function loadTrace() {
    if (!snapshot.value) {
      return;
    }
    traceLoading.value = true;
    error.value = "";
    try {
      trace.value = await getCaseTrace(snapshot.value.case.id);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "加载 Trace 失败";
    } finally {
      traceLoading.value = false;
    }
  }

  async function openTraceDebug() {
    if (!snapshot.value) {
      return;
    }
    debugMode.value = true;
    window.history.replaceState(null, "", "?debug=trace");
    await loadTrace();
  }

  function closeTraceDebug() {
    debugMode.value = false;
    window.history.replaceState(null, "", window.location.pathname);
  }

  async function downloadTrace() {
    if (!snapshot.value) {
      return;
    }
    traceLoading.value = true;
    error.value = "";
    try {
      const blob = await exportCaseTrace(snapshot.value.case.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "agent-trace.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "导出 Trace 失败";
    } finally {
      traceLoading.value = false;
    }
  }

  return {
    caseTitle,
    draftMessage,
    loading,
    uploadLoading,
    reportLoading,
    traceLoading,
    error,
    snapshot,
    trace,
    debugMode,
    progressItems,
    activeDatasetId,
    latestDatasetName,
    hasDataset,
    displayMessages,
    caseStateText,
    createNewCase,
    uploadFile,
    sendCurrentMessage,
    generateReport,
    loadTrace,
    openTraceDebug,
    closeTraceDebug,
    downloadTrace
  };
}
