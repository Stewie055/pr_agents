import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import App from "./App.vue";

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload
  };
}

function streamResponse(events: Array<{ event: string; data: unknown }>) {
  const text = events.map((item) => `event: ${item.event}\ndata: ${JSON.stringify(item.data)}\n\n`).join("");
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(text));
        controller.close();
      }
    })
  };
}

function caseSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    case: { id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" },
    datasets: [],
    messages: [],
    artifacts: [],
    evidence: [],
    tasks: [],
    tool_traces: [],
    ...overrides
  };
}

describe("App", () => {
  it("renders the diagnostic workspace", () => {
    const wrapper = mount(App);
    expect(wrapper.text()).toContain("半导体设备性能诊断");
    expect(wrapper.text()).toContain("辅助诊断对话");
    expect(wrapper.text()).toContain("诊断工作台");
    expect(wrapper.text()).not.toContain("Agent 调试台");
  });

  it("creates a case through the API", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot()));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/cases", expect.objectContaining({ method: "POST" }));
    expect(wrapper.text()).toContain("generic_semiconductor_tool");
    expect(wrapper.text()).toContain("等待上传设备性能 CSV");
  });

  it("shows dataset filename without exposing dataset id", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({ datasets: [{ id: "ds_secret123", filename: "performance.csv" }] })));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("数据已就绪：performance.csv");
    expect(wrapper.text()).not.toContain("ds_secret123");
  });

  it("shows API error details", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot()))
      .mockResolvedValueOnce(streamResponse([{ event: "error", data: { detail: "模型服务暂时不可用" } }]));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find(".composer button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("模型服务暂时不可用");
  });

  it("streams progress and assistant deltas", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({ datasets: [{ id: "ds_secret123", filename: "performance.csv" }] })))
      .mockResolvedValueOnce(streamResponse([
        { event: "started", data: { message: "开始处理请求" } },
        { event: "tool_start", data: { tool_name: "inspect_dataset" } },
        { event: "tool_result", data: { tool_name: "inspect_dataset", summary: "完成字段检查" } },
        { event: "message_delta", data: { delta: "诊断" } },
        { event: "message_delta", data: { delta: "完成" } },
        {
          event: "final",
          data: {
            message: { id: "msg_1", role: "assistant", content: "诊断完成" },
            summary: "诊断完成",
            artifacts: [],
            tool_traces: []
          }
        }
      ]))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({
        datasets: [{ id: "ds_secret123", filename: "performance.csv" }],
        messages: [{ id: "msg_1", role: "assistant", content: "诊断完成" }]
      })));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();
    await wrapper.find(".composer button").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/cases/case_1/messages/stream", expect.objectContaining({ method: "POST" }));
    expect(wrapper.text()).toContain("完成字段检查");
    expect(wrapper.text()).toContain("诊断完成");
  });

  it("shows case tasks and cancels pending tasks", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({
        tasks: [{ id: "task_pending", name: "csv.generate_report", status: "pending", artifact_ids: [] }]
      })))
      .mockResolvedValueOnce(jsonResponse({ id: "task_pending", name: "csv.generate_report", status: "cancelled" }))
      .mockResolvedValueOnce(jsonResponse({
        tasks: [{ id: "task_pending", name: "csv.generate_report", status: "cancelled", artifact_ids: [] }]
      }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({
        tasks: [{ id: "task_pending", name: "csv.generate_report", status: "cancelled", artifact_ids: [] }]
      })));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("生成 PPT 报告");
    expect(wrapper.text()).toContain("排队中");
    await wrapper.find(".task-list button").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/tasks/task_pending/cancel", { method: "POST" });
    expect(fetchMock).toHaveBeenCalledWith("/api/tasks?case_id=case_1");
    expect(wrapper.text()).toContain("已取消");
  });

  it("refreshes tasks and artifacts after streamed task results", async () => {
    const initialSnapshot = caseSnapshot({ datasets: [{ id: "ds_secret123", filename: "performance.csv" }] });
    const completedSnapshot = caseSnapshot({
      datasets: [{ id: "ds_secret123", filename: "performance.csv" }],
      tasks: [{ id: "task_chart", name: "csv.build_trend_chart", status: "succeeded", artifact_ids: ["art_chart_secret"] }],
      artifacts: [
        {
          id: "art_chart_secret",
          kind: "chart",
          title: "Temperature trend",
          summary: "Generated Matplotlib trend plot.",
          data: { render_type: "image", display_group: "Metric Trend", order: 1 }
        }
      ]
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/cases") {
        return Promise.resolve(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }));
      }
      if (url === "/api/cases/case_1") {
        return Promise.resolve(jsonResponse(completedSnapshot));
      }
      if (url === "/api/tasks?case_id=case_1") {
        return Promise.resolve(jsonResponse({
          tasks: [{ id: "task_chart", name: "csv.build_trend_chart", status: "succeeded", artifact_ids: ["art_chart_secret"] }]
        }));
      }
      if (url === "/api/cases/case_1/messages/stream") {
        return Promise.resolve(streamResponse([
          { event: "started", data: { message: "开始处理请求" } },
          { event: "tool_result", data: { tool_name: "build_trend_chart", summary: "submitted", task_ids: ["task_chart"] } },
          {
            event: "final",
            data: {
              message: { id: "msg_1", role: "assistant", content: "已提交图表任务" },
              summary: "已提交图表任务",
              artifacts: [],
              tool_traces: []
            }
          }
        ]));
      }
      return Promise.resolve(jsonResponse(initialSnapshot));
    });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();
    await wrapper.find(".composer button").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/tasks?case_id=case_1");
    expect(wrapper.text()).toContain("已生成 1 个产物");
    await wrapper.findAll("button").find((button) => button.text() === "图表")?.trigger("click");
    expect(wrapper.text()).toContain("Temperature trend");
  });

  it("renders chart gallery and report download assets", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({
        datasets: [{ id: "ds_secret123", filename: "performance.csv" }],
        artifacts: [
          {
            id: "art_chart_secret",
            kind: "chart",
            title: "Temperature trend",
            summary: "Generated Matplotlib trend plot.",
            data: { render_type: "image", display_group: "Metric Trend", order: 1 }
          },
          {
            id: "art_report_secret",
            kind: "report",
            title: "Diagnostic report deck",
            summary: "Generated an editable PPTX diagnostic report.",
            data: {
              format: "pptx",
              sections: [{ heading: "Executive Summary", body: "Report body" }]
            }
          }
        ]
      })));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();
    await wrapper.findAll("button").find((button) => button.text() === "图表")?.trigger("click");

    expect(wrapper.text()).toContain("图表");
    expect(wrapper.find(".chart-viewer img").attributes("src")).toBe("/api/artifacts/art_chart_secret/file");
    await wrapper.findAll("button").find((button) => button.text() === "报告")?.trigger("click");
    expect(wrapper.text()).toContain("PPT 报告");
    expect(wrapper.find(".report-download a").attributes("href")).toBe("/api/artifacts/art_report_secret/file");
    expect(wrapper.text()).not.toContain("ds_secret123");
  });

  it("loads the trace debug timeline on demand", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" }))
      .mockResolvedValueOnce(jsonResponse(caseSnapshot({ agent_steps: [] })))
      .mockResolvedValueOnce(jsonResponse({
          case: { id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" },
          messages: [],
          artifacts: [],
          evidence: [],
          tool_traces: [],
          agent_steps: [{ id: "step_1", step_index: 1, phase: "observe", duration_ms: 8 }],
          llm_audit_events: [{ id: "llm_1", provider: "openai_compatible", model: "mock", request: {}, response: {}, duration_ms: 8, created_at: "now" }]
        }));
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();
    const debugButton = wrapper.findAll("button").find((button) => button.text() === "调试 Trace");
    await debugButton?.trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/cases/case_1/trace");
    expect(wrapper.text()).toContain("Agent 调试台");
    expect(wrapper.text()).toContain("1 · observe");
    expect(wrapper.text()).toContain("openai_compatible / mock");
  });
});
