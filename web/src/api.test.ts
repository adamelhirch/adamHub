import { buildRuntimeRequestConfig } from "./api";
import { saveApiConfig } from "./config";

describe("api runtime config", () => {
  it("injects X-API-Key from localStorage", () => {
    saveApiConfig({ apiUrl: "http://localhost:8000", apiKey: "unit-test-key" });

    const runtime = buildRuntimeRequestConfig();

    expect(runtime.baseURL).toBe("http://localhost:8000");
    expect(runtime.apiKey).toBe("unit-test-key");
  });
});
