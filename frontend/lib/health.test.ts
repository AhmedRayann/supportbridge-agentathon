import { afterEach, describe, expect, it, vi } from "vitest";
import { getHealth } from "./health";

afterEach(() => vi.unstubAllGlobals());

describe("Python health client", () => {
  it("accepts the backend contract through the same-origin route", async () => {
    const body = { status: "ok", service: "supportbridge-api" };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(body));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getHealth()).resolves.toEqual(body);
    expect(fetchMock).toHaveBeenCalledWith("/svc/api/health", expect.objectContaining({ cache: "no-store" }));
  });

  it("rejects HTTP errors instead of reporting a connected API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    await expect(getHealth()).rejects.toThrow("Health request failed");
  });

  it.each([null, { status: "ok" }, { status: "error", service: "supportbridge-api" }])(
    "rejects an invalid health payload: %j", async (body) => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body)));
      await expect(getHealth()).rejects.toThrow("Unexpected health response");
    },
  );

  it("propagates a network failure for the UI error state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(getHealth()).rejects.toThrow("Failed to fetch");
  });
});
