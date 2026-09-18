import { useRef, useState } from "react";
import { SendIcon } from "./icons";

interface ComposerProps {
  disabled: boolean;
  onSend: (question: string) => void;
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    requestAnimationFrame(() => {
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    });
  }

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2 shadow-sm transition focus-within:border-indigo-300 focus-within:ring-1 focus-within:ring-indigo-300 dark:border-zinc-700 dark:bg-zinc-900 dark:focus-within:border-indigo-600">
      <textarea
        ref={textareaRef}
        value={value}
        rows={1}
        placeholder="Ask anything..."
        className="max-h-40 flex-1 resize-none bg-transparent py-1.5 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100 dark:placeholder:text-zinc-500"
        onChange={(e) => {
          setValue(e.target.value);
          e.target.style.height = "auto";
          e.target.style.height = `${e.target.scrollHeight}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="mb-0.5 shrink-0 rounded-lg bg-indigo-600 p-2 text-white transition enabled:hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400 dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600"
        title="Send"
      >
        <SendIcon />
      </button>
    </div>
  );
}
