const STATUS_STYLES = {
  pending: "bg-slate-100 text-slate-500",
  running: "bg-blue-100 text-blue-700",
  retrying: "bg-amber-100 text-amber-700",
  success: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  rolled_back: "bg-purple-100 text-purple-700",
};

function StatusPill({ status }) {
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${
        STATUS_STYLES[status] || "bg-slate-100 text-slate-500"
      }`}
    >
      {status}
    </span>
  );
}

export default function ExecutionLog({ events, steps }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Live Execution</h3>
        <span className="text-xs text-slate-400">{events.length} events</span>
      </div>

      {steps.length > 0 && (
        <div className="px-4 py-3 border-b border-slate-100 space-y-2 bg-slate-50/60">
          {steps.map((s) => (
            <div key={s.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[11px] text-slate-400 shrink-0">{s.tool}</span>
                <span className="truncate text-slate-700">{s.description}</span>
              </div>
              <StatusPill status={s.status} />
            </div>
          ))}
        </div>
      )}

      <div className="p-4 max-h-72 overflow-y-auto space-y-1.5 font-mono text-[12px] leading-relaxed">
        {events.length === 0 && <p className="text-slate-400">Logs will stream here once you run a workflow…</p>}
        {events.map((e, i) => (
          <div key={i} className="text-slate-600">
            <span className="text-slate-400">[{new Date(e.timestamp).toLocaleTimeString()}]</span>{" "}
            <span className="text-weave-600 font-semibold">{e.type}</span>{" "}
            <span className="text-slate-500">
              {e.payload?.description || e.payload?.error || summarize(e.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function summarize(payload) {
  if (!payload) return "";
  if (payload.status) return `status=${payload.status}`;
  if (payload.rolled_back_step_ids) return `rolled back ${payload.rolled_back_step_ids.length} step(s)`;
  return "";
}
