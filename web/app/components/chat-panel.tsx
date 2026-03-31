"use client";

import { ChangeEvent, FormEvent, RefObject } from "react";

import { Session } from "../types";

type ChatPanelProps = {
  theme: "dark" | "light";
  activeSession: Session;
  hasStarted: boolean;
  isSending: boolean;
  draft: string;
  pendingFiles: string[];
  models: string[];
  fileInputRef: RefObject<HTMLInputElement | null>;
  messageViewportRef: RefObject<HTMLDivElement | null>;
  onToggleTheme: () => void;
  onDraftChange: (value: string) => void;
  onFilePick: (event: ChangeEvent<HTMLInputElement>) => void;
  onSendMessage: (event: FormEvent) => Promise<void>;
  onModelChange: (value: string) => void;
};

export function ChatPanel({
  theme,
  activeSession,
  hasStarted,
  isSending,
  draft,
  pendingFiles,
  models,
  fileInputRef,
  messageViewportRef,
  onToggleTheme,
  onDraftChange,
  onFilePick,
  onSendMessage,
  onModelChange
}: ChatPanelProps) {
  return (
    <section className="relative flex min-h-screen flex-1 flex-col overflow-hidden">
      <header className="flex items-center justify-between border-b mono-border px-5 py-4 lg:px-8">
        <div>
          <p className="text-[0.72rem] uppercase tracking-[0.3em] text-[var(--muted)]">seju-lite runtime</p>
          <h1 className="mt-1 text-lg">Minimal chat workspace</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleTheme}
            className="rounded-full border mono-border px-4 py-2 text-xs uppercase tracking-[0.18em] transition hover:bg-[var(--fg)] hover:text-[var(--bg)]"
          >
            {theme === "dark" ? "White" : "Black"}
          </button>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        <div
          ref={messageViewportRef}
          className="thin-scrollbar h-full overflow-y-auto px-5 pb-48 pt-10 lg:px-8"
        >
          {!hasStarted ? (
            <div className="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center pb-32">
              <div className="max-w-3xl">
                <p className="text-[0.74rem] uppercase tracking-[0.34em] text-[var(--muted)]">
                  Openwebui-inspired entry
                </p>
                <h2 className="mt-4 max-w-2xl text-4xl font-light leading-tight lg:text-6xl">
                  A quiet shell for agent chat, files, and model switching.
                </h2>
                <p className="mt-5 max-w-xl text-sm leading-7 text-[var(--muted)] lg:text-base">
                  The first viewport stays almost empty on purpose. One field, one action, one place to
                  start the conversation.
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 pt-4">
              {activeSession.messages.map((message) => (
                <article
                  key={message.id}
                  className={`max-w-3xl ${message.role === "user" ? "ml-auto text-right" : "mr-auto"}`}
                >
                  <p className="mb-2 text-[0.68rem] uppercase tracking-[0.26em] text-[var(--muted)]">
                    {message.role}
                  </p>
                  <div
                    className={`rounded-[2rem] border px-5 py-4 text-sm leading-7 lg:text-[15px] ${
                      message.role === "user"
                        ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--bg)]"
                        : "mono-border"
                    }`}
                  >
                    {message.content}
                  </div>
                </article>
              ))}
              {isSending ? (
                <div className="max-w-3xl rounded-[2rem] border mono-border px-5 py-4 text-sm text-[var(--muted)]">
                  seju is thinking...
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
          style={{
            background:
              "linear-gradient(to top, var(--bg) 0%, color-mix(in srgb, var(--bg) 92%, transparent) 45%, transparent 100%)"
          }}
          aria-hidden="true"
        />

        <div
          className="absolute inset-x-0 bottom-0 px-4 pb-4 transition-transform duration-700 ease-soft lg:px-8 lg:pb-6"
          style={{
            transform: hasStarted
              ? "translate3d(0, 0, 0)"
              : "translate3d(0, calc(-42vh + 8rem), 0)"
          }}
        >
          <div className="mx-auto max-w-4xl">
            <form
              onSubmit={onSendMessage}
              className="glass-surface rounded-[2rem] border mono-border p-3 shadow-panel"
            >
              <div className="flex flex-wrap items-center gap-2 border-b mono-border px-2 pb-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-full border mono-border px-3 py-2 text-sm transition hover:bg-[var(--fg)] hover:text-[var(--bg)]"
                >
                  +
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={onFilePick}
                />
                <select
                  value={activeSession.model}
                  onChange={(event) => onModelChange(event.target.value)}
                  className="rounded-full border mono-border bg-transparent px-4 py-2 text-sm outline-none transition hover:border-[var(--fg)]"
                >
                  {models.map((model) => (
                    <option key={model} value={model} className="bg-black text-white">
                      {model}
                    </option>
                  ))}
                </select>
                <div className="ml-auto flex flex-wrap justify-end gap-2">
                  {pendingFiles.map((file) => (
                    <span
                      key={file}
                      className="rounded-full border mono-border px-3 py-1 text-[0.72rem] text-[var(--muted)]"
                    >
                      {file}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-end gap-3 px-2 pt-3">
                <textarea
                  value={draft}
                  onChange={(event) => onDraftChange(event.target.value)}
                  placeholder="Ask seju-lite to search, read, route, or act."
                  rows={hasStarted ? 2 : 6}
                  className="min-h-[3.75rem] flex-1 resize-none bg-transparent px-1 py-2 text-base leading-7 outline-none placeholder:text-[var(--muted)] lg:text-lg"
                />
                <button
                  type="submit"
                  disabled={isSending || draft.trim().length === 0}
                  className="rounded-full border border-[var(--fg)] bg-[var(--fg)] px-5 py-3 text-sm text-[var(--bg)] transition disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Send
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}
