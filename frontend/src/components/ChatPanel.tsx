import { useEffect, useRef, useState } from "react";
import { streamChat } from "../lib/api";
import type { ChatMessage, Project, StreamEvent } from "../lib/types";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";

interface ChatPanelProps {
  project: Project;
}

function activityFor(tool: string): string {
  if (tool === "knowledge_search") return "Searching your documents...";
  if (tool === "web_search") return "Searching the web...";
  if (tool === "web_fetch") return "Reading a source...";
  return "Working...";
}

export function ChatPanel({ project }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => abortRef.current?.();
  }, [project.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function handleSend(question: string) {
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: question,
      citations: [],
      status: "done",
    };
    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      text: "",
      citations: [],
      status: "streaming",
      activity: "Thinking...",
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setBusy(true);

    function updateAssistant(update: Partial<ChatMessage>) {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, ...update } : m)),
      );
    }

    function onEvent(event: StreamEvent) {
      switch (event.type) {
        case "tool_started":
          updateAssistant({ activity: activityFor(event.tool) });
          break;
        case "tool_finished":
          break;
        case "token":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, text: m.text + event.text, activity: undefined } : m,
            ),
          );
          break;
        case "citation":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, citations: [...m.citations, event.citation] } : m,
            ),
          );
          break;
        case "agent_finished":
          // event.answer is the source of truth (covers models that don't
          // stream tokens at all), but don't clobber already-streamed text
          // with an empty value.
          updateAssistant({
            ...(event.answer ? { text: event.answer } : {}),
            status: "done",
            activity: undefined,
          });
          break;
        case "error":
          updateAssistant({ status: "error", activity: undefined, text: event.message });
          break;
      }
    }

    abortRef.current = streamChat(
      project.id,
      question,
      onEvent,
      () => setBusy(false),
      (message) => {
        updateAssistant({ status: "error", activity: undefined, text: message });
        setBusy(false);
      },
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-center border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
        <h1 className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{project.name}</h1>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
          {messages.length === 0 && (
            <p className="text-sm text-zinc-400 dark:text-zinc-600">
              Ask a question about this project's documents, or the web.
            </p>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>
      </div>

      <div className="shrink-0 border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div className="mx-auto max-w-3xl">
          <Composer disabled={busy} onSend={handleSend} />
        </div>
      </div>
    </div>
  );
}
