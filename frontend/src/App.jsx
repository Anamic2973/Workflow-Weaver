import { useEffect, useState } from "react";
import WorkflowInput from "./components/WorkflowInput.jsx";
import TemplateLibrary from "./components/TemplateLibrary.jsx";
import ExecutionLog from "./components/ExecutionLog.jsx";
import ExecutionReport from "./components/ExecutionReport.jsx";
import { fetchTemplates, startRun, streamRun } from "./api.js";

export default function App() {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [description, setDescription] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [events, setEvents] = useState([]);
  const [steps, setSteps] = useState([]);
  const [report, setReport] = useState(null);

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  function handleSelectTemplate(t) {
    setSelectedTemplate(t);
    setDescription(t.example_prompt);
  }

  async function handleRun() {
    setIsRunning(true);
    setEvents([]);
    setSteps([]);
    setReport(null);

    try {
      const { run_id } = await startRun({
        description,
        template_id: selectedTemplate?.id,
      });

      streamRun(
        run_id,
        (evt) => {
          setEvents((prev) => [...prev, evt]);

          if (evt.type === "plan" && evt.payload.steps) {
            setSteps(evt.payload.steps);
          }
          if (evt.type === "step_update") {
            setSteps((prev) => {
              const idx = prev.findIndex((s) => s.id === evt.payload.id);
              if (idx === -1) return prev;
              const next = [...prev];
              next[idx] = { ...next[idx], ...evt.payload };
              return next;
            });
          }
          if (evt.type === "report") {
            setReport(evt.payload);
          }
        },
        () => setIsRunning(false)
      );
    } catch (e) {
      setIsRunning(false);
      setEvents((prev) => [
        ...prev,
        { type: "error", timestamp: new Date().toISOString(), payload: { error: e.message } },
      ]);
    }
  }

  return (
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-weave-600 flex items-center justify-center text-white font-bold">
            W
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-800">WorkflowWeaver</h1>
            <p className="text-xs text-slate-400">Describe a workflow. Watch the agent run it.</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <section>
          <h2 className="text-sm font-semibold text-slate-600 mb-3">Templates</h2>
          <TemplateLibrary
            templates={templates}
            onSelect={handleSelectTemplate}
            selectedId={selectedTemplate?.id}
          />
        </section>

        <section>
          <WorkflowInput
            value={description}
            onChange={setDescription}
            onRun={handleRun}
            isRunning={isRunning}
          />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ExecutionLog events={events} steps={steps} />
          <ExecutionReport report={report} />
        </section>
      </main>
    </div>
  );
}
