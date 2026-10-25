const BASE = "/api";

export async function fetchTemplates() {
  const res = await fetch(`${BASE}/templates`);
  if (!res.ok) throw new Error("Failed to load templates");
  return res.json();
}

export async function startRun({ description, template_id, config = {} }) {
  const res = await fetch(`${BASE}/workflows/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, template_id, config }),
  });
  if (!res.ok) throw new Error("Failed to start workflow run");
  return res.json(); // { run_id }
}

/**
 * Opens an SSE connection for a run and invokes onEvent for every event.
 * Returns a cleanup function to close the connection.
 */
export function streamRun(runId, onEvent, onDone) {
  const source = new EventSource(`${BASE}/workflows/stream/${runId}`);

  const types = ["plan", "step_start", "step_update", "step_end", "rollback", "report", "error"];
  types.forEach((type) => {
    source.addEventListener(type, (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        /* ignore malformed event */
      }
    });
  });

  source.addEventListener("done", () => {
    source.close();
    onDone?.();
  });

  source.onerror = () => {
    source.close();
    onDone?.();
  };

  return () => source.close();
}

export async function fetchReport(runId) {
  const res = await fetch(`${BASE}/workflows/${runId}/report`);
  if (!res.ok) throw new Error("Report not ready");
  return res.json();
}
