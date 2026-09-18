import type { Project, ProjectDocument, StreamEvent } from "./types";

const BASE = "/api/v1";

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listProjects: (): Promise<Project[]> =>
    fetch(`${BASE}/projects`).then((res) => unwrap<Project[]>(res)),

  createProject: (name: string, description = ""): Promise<Project> =>
    fetch(`${BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    }).then((res) => unwrap<Project>(res)),

  deleteProject: (projectId: string): Promise<void> =>
    fetch(`${BASE}/projects/${projectId}`, { method: "DELETE" }).then((res) => unwrap<void>(res)),

  listDocuments: (projectId: string): Promise<ProjectDocument[]> =>
    fetch(`${BASE}/projects/${projectId}/documents`).then((res) => unwrap<ProjectDocument[]>(res)),

  addDocument: (projectId: string, file: File): Promise<ProjectDocument> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(`${BASE}/projects/${projectId}/documents`, {
      method: "POST",
      body: formData,
    }).then((res) => unwrap<ProjectDocument>(res));
  },

  getDocument: (documentId: string): Promise<ProjectDocument> =>
    fetch(`${BASE}/documents/${documentId}`).then((res) => unwrap<ProjectDocument>(res)),

  deleteDocument: (documentId: string): Promise<void> =>
    fetch(`${BASE}/documents/${documentId}`, { method: "DELETE" }).then((res) => unwrap<void>(res)),
};

/** Streams a chat turn via SSE, invoking `onEvent` for each parsed event.
 * Returns an abort function. */
export function streamChat(
  projectId: string,
  question: string,
  onEvent: (event: StreamEvent) => void,
  onDone: () => void,
  onError: (message: string) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const url = `${BASE}/projects/${projectId}/chat/stream?question=${encodeURIComponent(question)}`;
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok || !res.body) {
        throw new Error(`${res.status} ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const event = JSON.parse(line.slice("data: ".length)) as StreamEvent;
          onEvent(event);
        }
      }
      onDone();
    } catch (err) {
      if (controller.signal.aborted) return;
      onError(err instanceof Error ? err.message : String(err));
    }
  })();

  return () => controller.abort();
}
