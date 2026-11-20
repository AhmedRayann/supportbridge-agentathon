export type Health = { status: "ok"; service: "supportbridge-api" };

export async function getHealth(): Promise<Health> {
  const response = await fetch("/svc/api/health", {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error("Health request failed.");

  const body: unknown = await response.json();
  if (
    typeof body !== "object" || body === null ||
    !("status" in body) || body.status !== "ok" ||
    !("service" in body) || body.service !== "supportbridge-api"
  ) {
    throw new Error("Unexpected health response.");
  }
  return { status: body.status, service: body.service };
}
