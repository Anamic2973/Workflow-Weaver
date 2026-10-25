const STATUS_BANNER = {
  success: { label: "Workflow completed successfully", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  partial_failure: { label: "Workflow completed with some failures", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  failed: { label: "Workflow failed — changes rolled back", cls: "bg-red-50 text-red-700 border-red-200" },
};

export default function ExecutionReport({ report }) {
  if (!report) return null;
  const banner = STATUS_BANNER[report.status] || STATUS_BANNER.failed;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className={`px-4 py-3 border-b text-sm font-semibold ${banner.cls}`}>{banner.label}</div>
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-slate-400 text-xs uppercase tracking-wide">Run ID</div>
            <div className="font-mono text-slate-700 text-xs mt-0.5">{report.run_id}</div>
          </div>
          <div>
            <div className="text-slate-400 text-xs uppercase tracking-wide">Steps</div>
            <div className="text-slate-700 mt-0.5">{report.steps?.length ?? 0}</div>
          </div>
        </div>

        {report.rolled_back_steps?.length > 0 && (
          <div className="text-sm text-purple-700 bg-purple-50 border border-purple-200 rounded-lg px-3 py-2">
            Rolled back {report.rolled_back_steps.length} step(s) to restore prior state.
          </div>
        )}

        {report.langfuse_trace_url && (
          <a
            href={report.langfuse_trace_url}
            target="_blank"
            rel="noreferrer"
            className="inline-block text-sm text-weave-600 hover:underline"
          >
            View full trace in Langfuse →
          </a>
        )}
      </div>
    </div>
  );
}
