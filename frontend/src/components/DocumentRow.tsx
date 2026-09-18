import type { ProjectDocument } from "../lib/types";
import { AlertIcon, DocumentIcon, SpinnerIcon, TrashIcon } from "./icons";

interface DocumentRowProps {
  document: ProjectDocument;
  onDelete: () => void;
}

export function DocumentRow({ document, onDelete }: DocumentRowProps) {
  return (
    <li
      className="group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-zinc-600 dark:text-zinc-300"
      title={document.error ?? undefined}
    >
      <span className="shrink-0 text-zinc-400 dark:text-zinc-500">
        {document.status === "FAILED" ? (
          <span className="text-red-500">
            <AlertIcon />
          </span>
        ) : document.status === "READY" ? (
          <DocumentIcon />
        ) : (
          <SpinnerIcon />
        )}
      </span>
      <span className="min-w-0 flex-1 truncate">{document.filename}</span>
      <span
        onClick={onDelete}
        className="shrink-0 rounded p-0.5 text-zinc-400 opacity-0 transition hover:bg-zinc-300 hover:text-zinc-700 group-hover:opacity-100 dark:hover:bg-zinc-700 dark:hover:text-zinc-200"
      >
        <TrashIcon />
      </span>
    </li>
  );
}
