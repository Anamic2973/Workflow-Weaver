export default function WorkflowInput({ value, onChange, onRun, isRunning }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
      <label className="text-sm font-medium text-slate-700 mb-2 block">
        Describe your workflow
      </label>
      <textarea
        className="w-full min-h-[110px] rounded-lg border border-slate-200 p-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-weave-400 resize-y"
        placeholder="e.g. Take today's meeting notes and create a Notion project page, generate action items, and post a summary to Microsoft Teams."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isRunning}
      />
      <div className="flex justify-end mt-3">
        <button
          onClick={onRun}
          disabled={isRunning || !value.trim()}
          className="px-4 py-2 rounded-lg bg-weave-600 text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-weave-700 transition-colors"
        >
          {isRunning ? "Running…" : "Run Workflow"}
        </button>
      </div>
    </div>
  );
}
