import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, Citation, DocumentCitation, WebCitation } from "../lib/types";
import { DocumentIcon, GlobeIcon, SpinnerIcon } from "./icons";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl bg-indigo-600 px-4 py-2 text-sm text-white">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {message.activity && (
        <div className="flex items-center gap-2 text-sm text-zinc-400 dark:text-zinc-500">
          <SpinnerIcon />
          <span>{message.activity}</span>
        </div>
      )}

      {message.text && (
        <div
          className={`prose prose-sm max-w-none prose-zinc dark:prose-invert prose-p:my-1.5 prose-pre:my-2 ${
            message.status === "error" ? "text-red-500 dark:text-red-400" : ""
          }`}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
          {message.status === "streaming" && (
            <span className="animate-blink text-zinc-400">▍</span>
          )}
        </div>
      )}

      {message.citations.length > 0 && <Sources citations={message.citations} />}
    </div>
  );
}

function Sources({ citations }: { citations: Citation[] }) {
  return (
    <div className="flex flex-wrap gap-1.5 pt-1">
      {citations.map((citation, i) =>
        citation.type === "web" ? (
          <WebSourceChip key={i} citation={citation} />
        ) : (
          <DocumentSourceChip key={i} citation={citation} />
        ),
      )}
    </div>
  );
}

function DocumentSourceChip({ citation }: { citation: DocumentCitation }) {
  const location =
    citation.page_number != null
      ? `p.${citation.page_number}`
      : citation.slide_number != null
        ? `slide ${citation.slide_number}`
        : null;

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
      title={citation.text}
    >
      <DocumentIcon />
      Document{location ? ` · ${location}` : ""}
    </span>
  );
}

function WebSourceChip({ citation }: { citation: WebCitation }) {
  let host = citation.url;
  try {
    host = new URL(citation.url).hostname.replace(/^www\./, "");
  } catch {
    // keep the raw url as a fallback label
  }

  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-600 transition hover:border-indigo-300 hover:text-indigo-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:border-indigo-600 dark:hover:text-indigo-400"
      title={citation.title ?? citation.url}
    >
      <GlobeIcon />
      {host}
    </a>
  );
}
