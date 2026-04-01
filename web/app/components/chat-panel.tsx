"use client";

import { ChangeEvent, FormEvent, RefObject, useEffect, useState } from "react";
import { useTheme } from "next-themes";

import { Session } from "../types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { ChevronDown, Moon, Paperclip, Sun } from "lucide-react";

type ChatPanelProps = {
  activeSession: Session;
  hasStarted: boolean;
  isSending: boolean;
  draft: string;
  pendingFiles: string[];
  models: string[];
  fileInputRef: RefObject<HTMLInputElement | null>;
  messageViewportRef: RefObject<HTMLDivElement | null>;
  onDraftChange: (value: string) => void;
  onFilePick: (event: ChangeEvent<HTMLInputElement>) => void;
  onSendMessage: (event: FormEvent) => Promise<void>;
  onModelChange: (value: string) => void;
};

export function ChatPanel({
  activeSession,
  hasStarted,
  isSending,
  draft,
  pendingFiles,
  models,
  fileInputRef,
  messageViewportRef,
  onDraftChange,
  onFilePick,
  onSendMessage,
  onModelChange
}: ChatPanelProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted ? resolvedTheme !== "light" : true;
  const composer = (
    <div className="mx-auto w-full max-w-4xl">
      <form
        onSubmit={onSendMessage}
        className="glass-surface rounded-[2rem] border mono-border p-3 shadow-panel"
      >
        <div className="flex flex-wrap items-center gap-2 border-b mono-border px-2 pb-3">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full border mono-border bg-transparent px-4 py-2 text-sm hover:bg-[var(--onhold)] hover:text-[var(--text)]"
                />
              }
            > 
              + 
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              side={hasStarted ? "top" : "bottom"}
              sideOffset={8}
              className="w-56 rounded-2xl bg-background/95 p-1 text-foreground shadow-lg backdrop-blur-md"
            >
              <DropdownMenuItem
                onClick={() => fileInputRef.current?.click()}
                className="rounded-xl text-[var(--app-muted)] transition-colors hover:bg-[var(--onhold)]/70 hover:text-[var(--text)] focus:bg-[var(--onhold)]/70 focus:text-[var(--text)]"
              >
                <Paperclip className="size-4" />
                <span>Upload files</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={onFilePick}
            />
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full border mono-border bg-transparent px-4 py-2 text-sm hover:bg-[var(--onhold)] hover:text-[var(--text)]"
                />
              }
            >
              <span className="truncate">{activeSession.model}</span>
              <ChevronDown className="size-4 opacity-70" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              side={hasStarted ? "top" : "bottom"}
              sideOffset={8}
              className="w-56 rounded-2xl p-1 text-foreground shadow-lg backdrop-blur-md"
            >
              <DropdownMenuRadioGroup
                value={activeSession.model}
                onValueChange={(value) => onModelChange(String(value))}
              >
                {models.map((model) => (
                  <DropdownMenuRadioItem
                    key={model}
                    value={model}
                    className={`rounded-xl transition-colors ${
                      model === activeSession.model
                        ? "bg-[var(--onhold)] text-[var(--text)] hover:bg-[var(--onhold)] focus:bg-[var(--onhold)] focus:text-[var(--text)]"
                        : "text-[var(--app-muted)] hover:bg-[var(--onhold)]/70 hover:text-[var(--text)] focus:bg-[var(--onhold)]/70 focus:text-[var(--text)]"
                    }`}
                  >
                    <span>{model}</span>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="ml-auto flex flex-wrap justify-end gap-2">
            {pendingFiles.map((file) => (
              <span
                key={file}
                className="rounded-full border mono-border px-3 py-1 text-[0.72rem] text-[var(--app-muted)]"
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
            className="min-h-[3.75rem] flex-1 resize-none bg-transparent px-1 py-2 text-base leading-7 outline-none placeholder:text-[var(--app-muted)] lg:text-lg"
          />
          <Button
            type="submit"
            disabled={isSending || draft.trim().length === 0}
            className="rounded-full border border-[var(--fg)] bg-[var(--fg)] px-5 py-3 text-sm text-[var(--bg)] transition hover:bg-[var(--fg)]/90"
          >
            Send
          </Button>
        </div>
      </form>
    </div>
  );

  return (
    <section className="relative flex h-screen flex-1 flex-col overflow-hidden">
      <header className="z-30 flex items-center justify-between border-b mono-border bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-5 py-4 backdrop-blur-md lg:px-8">
        <div>
          <p className="text-[0.72rem] uppercase tracking-[0.3em] text-[var(--app-muted)]">seju-lite runtime</p>
          <h1 className="mt-1 text-lg">Minimal chat workspace</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={() => setTheme(isDark ? "light" : "dark")}
            aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
            title={isDark ? "Switch to light theme" : "Switch to dark theme"}
            className="rounded-full border mono-border bg-transparent hover:bg-[var(--onhold)] hover:text-[var(--fg)]"
          >
            {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>
      </header>

      <div className="relative flex-1 overflow-hidden">
        <div
          ref={messageViewportRef}
          className={`thin-scrollbar h-full overflow-y-auto px-5 lg:px-8 ${
            hasStarted ? "pt-10 pb-[42svh] lg:pb-[34svh]" : "py-0"
          }`}
        >
          {!hasStarted ? (
            <div className="mx-auto flex min-h-full w-full max-w-5xl items-center justify-center py-10">
              <div className="flex w-full max-w-4xl flex-col items-center text-center">
                  <p className="text-[0.74rem] uppercase tracking-[0.34em] text-[var(--app-muted)]">
                    Openwebui-inspired entry
                  </p>
                  <h2 className="mt-4 max-w-3xl text-3xl font-light leading-tight lg:text-5xl">
                    How can I assist you today?
                  </h2>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--app-muted)] lg:text-base">
                    Start with a task, a file, or a question. The workspace stays quiet until the first
                    message.
                  </p>
                  <div className="mt-8 w-full">{composer}</div>
              </div>
            </div>
          ) : (
            <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 pt-4">
              {activeSession.messages.map((message) => (
                <article
                  key={message.id}
                  className={`max-w-3xl ${message.role === "user" ? "ml-auto text-right" : "mr-auto"}`}
                >
                  <p className="mb-2 text-[0.68rem] uppercase tracking-[0.26em] text-[var(--app-muted)]">
                    {message.role}
                  </p>
                  <div
                    className={`rounded-[2rem] px-5 py-4 text-sm leading-7 lg:text-[15px] ${
                      message.role === "user"
                        ? "bg-[var(--onhold)] text-[var(--text)]"
                        : "mono-border"
                    }`}
                  >
                    {message.content}
                  </div>
                </article>
              ))}
              {isSending ? (
                <div className="max-w-3xl rounded-[2rem] border mono-border px-5 py-4 text-sm text-[var(--app-muted)]">
                  seju is thinking...
                </div>
              ) : null}
            </div>
          )}
        </div>

        {hasStarted ? (
          <>
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-48"
              style={{
                background:
                  "linear-gradient(to top, var(--bg) 0%, color-mix(in srgb, var(--bg) 92%, transparent) 45%, transparent 100%)"
              }}
              aria-hidden="true"
            />

            <div className="absolute inset-x-0 bottom-0 z-20 px-4 pb-4 transition-all duration-700 ease-soft lg:px-8 lg:pb-6">
              {composer}
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}
