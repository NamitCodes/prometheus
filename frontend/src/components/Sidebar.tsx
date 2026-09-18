import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Project, ProjectDocument } from "../lib/types";
import { DocumentRow } from "./DocumentRow";
import { PlusIcon, TrashIcon } from "./icons";

interface SidebarProps {
  activeProject: Project | null;
  onSelectProject: (project: Project) => void;
}

export function Sidebar({ activeProject, onSelectProject }: SidebarProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [loadError, setLoadError] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  function loadProjects() {
    setLoadError(false);
    api.listProjects().then(setProjects).catch(() => setLoadError(true));
  }

  useEffect(() => {
    if (!activeProject) {
      setDocuments([]);
      return;
    }
    refreshDocuments(activeProject.id);
  }, [activeProject]);

  // Poll while any document is still processing, so status updates without a refresh.
  useEffect(() => {
    if (!activeProject) return;
    const inFlight = documents.some((d) => d.status !== "READY" && d.status !== "FAILED");
    if (!inFlight) return;
    const timer = setInterval(() => refreshDocuments(activeProject.id), 2000);
    return () => clearInterval(timer);
  }, [activeProject, documents]);

  function refreshDocuments(projectId: string) {
    api.listDocuments(projectId).then(setDocuments).catch(() => {});
  }

  async function handleCreateProject() {
    const name = newName.trim();
    if (!name) return;
    const project = await api.createProject(name);
    setProjects((prev) => [project, ...prev]);
    setNewName("");
    setCreating(false);
    onSelectProject(project);
  }

  async function handleDeleteProject(project: Project, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm(`Delete project "${project.name}"? This deletes its documents too.`)) return;
    await api.deleteProject(project.id);
    setProjects((prev) => prev.filter((p) => p.id !== project.id));
    if (activeProject?.id === project.id) {
      const remaining = projects.filter((p) => p.id !== project.id);
      if (remaining.length > 0) onSelectProject(remaining[0]);
    }
  }

  async function handleFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !activeProject) return;
    const doc = await api.addDocument(activeProject.id, file);
    setDocuments((prev) => [doc, ...prev]);
  }

  async function handleDeleteDocument(doc: ProjectDocument) {
    await api.deleteDocument(doc.id);
    setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between px-4 py-4">
        <span className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
          Prometheus
        </span>
        <button
          onClick={() => setCreating(true)}
          className="rounded-md p-1.5 text-zinc-500 transition hover:bg-zinc-200 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          title="New project"
        >
          <PlusIcon />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        <div className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Projects
        </div>

        {creating && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreateProject();
            }}
            className="px-2 pb-1"
          >
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onBlur={() => !newName && setCreating(false)}
              placeholder="Project name"
              className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:focus:border-indigo-500"
            />
          </form>
        )}

        <ul className="flex flex-col gap-0.5">
          {projects.map((project) => (
            <li key={project.id}>
              <button
                onClick={() => onSelectProject(project)}
                className={`group flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm transition ${
                  activeProject?.id === project.id
                    ? "bg-indigo-100 text-indigo-900 dark:bg-indigo-500/15 dark:text-indigo-200"
                    : "text-zinc-600 hover:bg-zinc-200/70 dark:text-zinc-300 dark:hover:bg-zinc-800"
                }`}
              >
                <span className="truncate">{project.name}</span>
                <span
                  onClick={(e) => handleDeleteProject(project, e)}
                  className="ml-2 shrink-0 rounded p-0.5 text-zinc-400 opacity-0 transition hover:bg-zinc-300 hover:text-zinc-700 group-hover:opacity-100 dark:hover:bg-zinc-700 dark:hover:text-zinc-200"
                >
                  <TrashIcon />
                </span>
              </button>
            </li>
          ))}
          {loadError && (
            <li className="flex items-center justify-between px-2 py-1.5 text-sm text-red-500">
              <span>Couldn't load projects</span>
              <button onClick={loadProjects} className="underline hover:no-underline">
                Retry
              </button>
            </li>
          )}
          {!loadError && projects.length === 0 && !creating && (
            <li className="px-2 py-1.5 text-sm text-zinc-400 dark:text-zinc-500">
              No projects yet
            </li>
          )}
        </ul>

        {activeProject && (
          <>
            <div className="mt-5 flex items-center justify-between px-2 pb-1">
              <span className="text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                Documents
              </span>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="rounded-md p-1 text-zinc-500 transition hover:bg-zinc-200 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                title="Upload document"
              >
                <PlusIcon />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.pptx,.txt"
                className="hidden"
                onChange={handleFileChosen}
              />
            </div>

            <ul className="flex flex-col gap-0.5">
              {documents.map((doc) => (
                <DocumentRow key={doc.id} document={doc} onDelete={() => handleDeleteDocument(doc)} />
              ))}
              {documents.length === 0 && (
                <li className="px-2 py-1.5 text-sm text-zinc-400 dark:text-zinc-500">
                  No documents yet
                </li>
              )}
            </ul>
          </>
        )}
      </div>
    </aside>
  );
}
