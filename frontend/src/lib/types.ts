export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export type DocumentStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "INDEXING"
  | "READY"
  | "FAILED";

export interface ProjectDocument {
  id: string;
  project_id: string;
  filename: string;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
}

export interface DocumentCitation {
  type: "document";
  chunk_id: string;
  document_id: string | null;
  project_id?: string | null;
  filename?: string | null;
  page_number: number | null;
  slide_number: number | null;
  text?: string;
  score?: number;
}

export interface WebCitation {
  type: "web";
  url: string;
  title: string | null;
}

export type Citation = DocumentCitation | WebCitation;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
  status: "streaming" | "done" | "error";
  activity?: string;
}

export type StreamEvent =
  | { type: "agent_started" }
  | { type: "tool_started"; tool: string }
  | { type: "tool_finished"; tool: string }
  | { type: "token"; text: string }
  | { type: "citation"; citation: Citation }
  | { type: "agent_finished"; answer: string }
  | { type: "error"; message: string };
