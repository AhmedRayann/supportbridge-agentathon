"use client";

import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/health";

type State = { kind: "loading" } | { kind: "ready"; health: Health } | { kind: "error" };

export default function Home() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth().then(
      (health) => { if (active) setState({ kind: "ready", health }); },
      () => { if (active) setState({ kind: "error" }); },
    );
    return () => { active = false; };
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-slate-900">
      <h1 className="text-3xl font-semibold">SupportBridge</h1>
      <p className="mt-3 text-base">Milestone 1A: frontend and Python API connection.</p>
      <section className="mt-8 rounded border border-slate-300 p-5" aria-labelledby="health-title">
        <h2 id="health-title" className="text-lg font-semibold">Backend health</h2>
        <div role="status" aria-live="polite" className="mt-3">
          {state.kind === "loading" && <p>Checking Python API…</p>}
          {state.kind === "ready" && (
            <><p>Python API connected.</p><pre className="mt-3 overflow-auto text-sm">{JSON.stringify(state.health, null, 2)}</pre></>
          )}
          {state.kind === "error" && (
            <p>Python API unavailable or returned an invalid response. Check the backend and reload to retry.</p>
          )}
        </div>
      </section>
    </main>
  );
}
