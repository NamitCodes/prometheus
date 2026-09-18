import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatPanel } from "./components/ChatPanel";
import type { Project } from "./lib/types";

export default function App() {
  const [activeProject, setActiveProject] = useState<Project | null>(null);

  return (
    <div className="flex h-full bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <Sidebar activeProject={activeProject} onSelectProject={setActiveProject} />
      <main className="flex min-w-0 flex-1 flex-col">
        {activeProject ? (
          <ChatPanel key={activeProject.id} project={activeProject} />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <div className="text-2xl font-semibold tracking-tight text-zinc-400 dark:text-zinc-600">
        Prometheus
      </div>
      <p className="max-w-xs text-sm text-zinc-400 dark:text-zinc-600">
        Select a project, or create one to start researching.
      </p>
    </div>
  );
}
