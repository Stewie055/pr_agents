import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import App from "./App.vue";

describe("App", () => {
  it("renders the diagnostic workspace", () => {
    const wrapper = mount(App);
    expect(wrapper.text()).toContain("半导体设备性能诊断");
    expect(wrapper.text()).toContain("辅助诊断对话");
    expect(wrapper.text()).toContain("证据与报告");
  });

  it("creates a case through the API", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          case: { id: "case_1", title: "demo", equipment_type: "generic_semiconductor_tool", status: "open" },
          datasets: [],
          messages: [],
          artifacts: [],
          tool_traces: []
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(App);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith("/api/cases", expect.objectContaining({ method: "POST" }));
    expect(wrapper.text()).toContain("generic_semiconductor_tool");
  });
});
