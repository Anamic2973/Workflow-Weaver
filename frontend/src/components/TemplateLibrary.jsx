export default function TemplateLibrary({ templates, onSelect, selectedId }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {templates.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t)}
          className={`text-left p-4 rounded-xl border transition-all ${
            selectedId === t.id
              ? "border-weave-500 bg-weave-50 ring-2 ring-weave-400"
              : "border-slate-200 bg-white hover:border-weave-300 hover:shadow-sm"
          }`}
        >
          <div className="font-semibold text-slate-800">{t.name}</div>
          <p className="text-sm text-slate-500 mt-1 leading-snug">{t.description}</p>
          <div className="flex gap-1.5 mt-3 flex-wrap">
            {t.tools_used.map((tool) => (
              <span
                key={tool}
                className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-weave-100 text-weave-700"
              >
                {tool.replace("_", " ")}
              </span>
            ))}
          </div>
        </button>
      ))}
    </div>
  );
}
