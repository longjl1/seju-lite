"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ChatPanel } from "./components/chat-panel";
import { Sidebar } from "./components/sidebar";
import { Message, Session, ThinkingStep, UploadedDocument } from "./types";

const MODELS = ["deepseek-chat", "gpt-4.1-mini", "gemini-2.0-flash"];
const STORAGE_KEY = "seju-lite-web-sessions";

const INTRO_MESSAGE =
  "seju.neo is a lightweight multi-agent runtime. Start with a task, a file, or a question and the workspace stays uncluttered.";

type ScheduleSummary = {
  id: string;
  name: string;
  prompt: string;
  every_seconds: number;
  channel: string;
  chat_id: string;
  user_id: string;
  enabled: boolean;
  run_immediately: boolean;
  created_at: string;
  updated_at: string;
  last_run_at?: string | null;
  last_result?: string | null;
};

function uid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function buildStarterSession(): Session {
  const now = new Date().toISOString();
  return {
    id: uid(),
    title: "New workspace",
    model: MODELS[0],
    updatedAt: now,
    uploads: [],
    scheduleReceipts: {},
    messages: [
      {
        id: uid(),
        role: "assistant",
        content: INTRO_MESSAGE
      }
    ]
  };
}

function normalizeUploads(uploads: unknown): UploadedDocument[] {
  if (!Array.isArray(uploads)) {
    return [];
  }

  const normalized: UploadedDocument[] = [];

  uploads.forEach((item) => {
    let nextItem: UploadedDocument | null = null;

    if (typeof item === "string") {
      nextItem = {
        id: item,
        name: item,
        status: "ready"
      };
    } else if (item && typeof item === "object") {
      const record = item as Partial<UploadedDocument>;
      const name = typeof record.name === "string" ? record.name : "";
      if (name) {
        nextItem = {
          id:
            typeof record.id === "string" && record.id
              ? record.id
              : Math.random().toString(36).slice(2),
          name,
          savedPath: typeof record.savedPath === "string" ? record.savedPath : undefined,
          relativePath: typeof record.relativePath === "string" ? record.relativePath : undefined,
          size: typeof record.size === "number" ? record.size : undefined,
          status:
            record.status === "uploading" || record.status === "error" || record.status === "ready"
              ? record.status
              : "ready",
          error: typeof record.error === "string" ? record.error : undefined,
          indexedAt: typeof record.indexedAt === "string" ? record.indexedAt : undefined
        };
      }
    }

    if (nextItem) {
      normalized.push(nextItem);
    }
  });

  return normalized;
}

function normalizeSessions(raw: Session[]): Session[] {
  return raw.map((session) => ({
    ...session,
    uploads: normalizeUploads(session.uploads),
    scheduleReceipts:
      session.scheduleReceipts && typeof session.scheduleReceipts === "object"
        ? session.scheduleReceipts
        : {},
    messages: Array.isArray(session.messages)
      ? session.messages.map((message) => ({
          ...message,
          thinkingSteps: Array.isArray(message.thinkingSteps)
            ? (message.thinkingSteps as ThinkingStep[])
            : undefined
        }))
      : []
  }));
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export default function HomePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [draft, setDraft] = useState("");
  const [pendingFiles, setPendingFiles] = useState<UploadedDocument[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messageViewportRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const storedSessions = window.localStorage.getItem(STORAGE_KEY);

    if (storedSessions) {
      try {
        const parsed = JSON.parse(storedSessions) as Session[];
        if (parsed.length > 0) {
          const normalized = normalizeSessions(parsed);
          setSessions(normalized);
          setActiveSessionId(normalized[0].id);
          setHasStarted(normalized[0].messages.length > 1);
        }
      } catch {
        const starter = buildStarterSession();
        setSessions([starter]);
        setActiveSessionId(starter.id);
      }
    } else {
      const starter = buildStarterSession();
      setSessions([starter]);
      setActiveSessionId(starter.id);
    }
  }, []);

  useEffect(() => {
    if (sessions.length > 0) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    }
  }, [sessions]);

  useEffect(() => {
    const viewport = messageViewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
  }, [activeSessionId, sessions]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? sessions[0],
    [activeSessionId, sessions]
  );

  useEffect(() => {
    if (activeSession) {
      setHasStarted(activeSession.messages.length > 1);
      setPendingFiles(activeSession.uploads);
    }
  }, [activeSession]);

  useEffect(() => {
    if (sessions.length === 0) {
      return;
    }

    let cancelled = false;

    const syncSchedules = async () => {
      try {
        const response = await fetch("/api/schedules", { cache: "no-store" });
        if (!response.ok) {
          return;
        }

        const tasks = (await response.json()) as ScheduleSummary[];
        if (cancelled || !Array.isArray(tasks)) {
          return;
        }

        tasks.forEach((task) => {
          if (!task.last_result || !task.last_run_at) {
            return;
          }
          appendScheduledResult(task.chat_id, task);
        });
      } catch {}
    };

    void syncSchedules();
    const timer = window.setInterval(() => {
      void syncSchedules();
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sessions.length]);

  const createNewSession = () => {
    const next = buildStarterSession();
    setSessions((current) => [next, ...current]);
    setActiveSessionId(next.id);
    setDraft("");
    setPendingFiles([]);
    setHasStarted(false);
  };

  const deleteSession = (sessionId: string) => {
    setSessions((current) => {
      const remaining = current.filter((session) => session.id !== sessionId);

      if (remaining.length === 0) {
        const next = buildStarterSession();
        setActiveSessionId(next.id);
        setDraft("");
        setPendingFiles([]);
        setHasStarted(false);
        return [next];
      }

      if (activeSessionId === sessionId) {
        setActiveSessionId(remaining[0].id);
      }

      return remaining;
    });
  };

  const updateActiveSession = (updater: (session: Session) => Session) => {
    setSessions((current) =>
      current.map((session) =>
        session.id === activeSessionId ? updater(session) : session
      )
    );
  };

  const updateSessionById = (
    sessionId: string,
    updater: (session: Session) => Session
  ) => {
    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId ? updater(session) : session
      )
    );
  };

  const appendScheduledResult = (sessionId: string, task: ScheduleSummary) => {
    if (!task.last_result || !task.last_run_at) {
      return;
    }

    const receipt = task.last_run_at;

    updateSessionById(sessionId, (session) => {
      const receipts = session.scheduleReceipts ?? {};
      if (receipts[task.id] === receipt) {
        return session;
      }

      return {
        ...session,
        updatedAt: receipt,
        scheduleReceipts: {
          ...receipts,
          [task.id]: receipt
        },
        messages: [
          ...session.messages,
          {
            id: uid(),
            role: "assistant",
            content: `Scheduled task: ${task.name}\n\n${task.last_result}`
          }
        ]
      };
    });
  };

  const appendAssistantContent = (
    sessionId: string,
    messageId: string,
    chunk: string
  ) => {
    updateSessionById(sessionId, (session) => ({
      ...session,
      updatedAt: new Date().toISOString(),
      messages: session.messages.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content: `${message.content}${chunk}`
            }
          : message
      )
    }));
  };

  const setAssistantMessage = (
    sessionId: string,
    messageId: string,
    updater: (message: Message) => Message
  ) => {
    updateSessionById(sessionId, (session) => ({
      ...session,
      updatedAt: new Date().toISOString(),
      messages: session.messages.map((message) =>
        message.id === messageId ? updater(message) : message
      )
    }));
  };

  const upsertThinkingStep = (
    sessionId: string,
    messageId: string,
    step: ThinkingStep
  ) => {
    setAssistantMessage(sessionId, messageId, (message) => {
      const current = message.thinkingSteps ?? [];
      const existingIndex = current.findIndex((item) => item.id === step.id);
      if (existingIndex === -1) {
        return {
          ...message,
          thinkingSteps: [...current, step]
        };
      }

      const next = [...current];
      next[existingIndex] = {
        ...next[existingIndex],
        ...step
      };
      return {
        ...message,
        thinkingSteps: next
      };
    });
  };

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0 || !activeSession) {
      return;
    }

    const conversationId = activeSession.id;
    const placeholders = files.map((file) => ({
      id: uid(),
      name: file.name,
      size: file.size,
      status: "uploading" as const
    }));

    const nextUploads = [...pendingFiles, ...placeholders];
    setPendingFiles(nextUploads);
    updateSessionById(conversationId, (session) => ({
      ...session,
      uploads: nextUploads,
      updatedAt: new Date().toISOString()
    }));

    await Promise.all(
      files.map(async (file, index) => {
        const placeholder = placeholders[index];
        const formData = new FormData();
        formData.append("conversation_id", conversationId);
        formData.append("file", file);

        try {
          const response = await fetch("/api/uploads", {
            method: "POST",
            body: formData
          });
          const payload = (await response.json()) as {
            file?: UploadedDocument;
            error?: string;
          };
          if (!response.ok || !payload.file) {
            throw new Error(payload.error || "Upload failed.");
          }

          updateSessionById(conversationId, (session) => {
            if (!session.uploads.some((item) => item.id === placeholder.id)) {
              return session;
            }
            const uploads = session.uploads.map((item) =>
              item.id === placeholder.id ? payload.file! : item
            );
            if (conversationId === activeSessionId) {
              setPendingFiles(uploads);
            }
            return {
              ...session,
              uploads,
              updatedAt: new Date().toISOString()
            };
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Upload failed.";
          updateSessionById(conversationId, (session) => {
            if (!session.uploads.some((item) => item.id === placeholder.id)) {
              return session;
            }
            const uploads = session.uploads.map((item) =>
              item.id === placeholder.id
                ? { ...item, status: "error" as const, error: message }
                : item
            );
            if (conversationId === activeSessionId) {
              setPendingFiles(uploads);
            }
            return {
              ...session,
              uploads,
              updatedAt: new Date().toISOString()
            };
          });
        }
      })
    );
  };

  const handleFilePick = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) {
      return;
    }

    await uploadFiles(files);
    event.target.value = "";
  };

  const removeUpload = async (uploadId: string) => {
    if (!activeSession) {
      return;
    }

    const upload = pendingFiles.find((item) => item.id === uploadId);
    if (!upload) {
      return;
    }

    if (upload.savedPath) {
      try {
        await fetch("/api/uploads", {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            conversation_id: activeSession.id,
            upload_id: upload.id
          })
        });
      } catch {}
    }

    const nextUploads = pendingFiles.filter((item) => item.id !== uploadId);
    setPendingFiles(nextUploads);
    updateActiveSession((session) => ({
      ...session,
      uploads: session.uploads.filter((item) => item.id !== uploadId),
      updatedAt: new Date().toISOString()
    }));
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();

    const content = draft.trim();
    if (!content || !activeSession) {
      return;
    }

    const userMessage: Message = { id: uid(), role: "user", content };
    const assistantMessageId = uid();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      isStreaming: true,
      thinkingSteps: [
        {
          id: "stream-init",
          kind: "status",
          title: "Preparing response",
          detail: "Connecting to the agent stream.",
          state: "info"
        }
      ]
    };
    const conversationId = activeSession.id;
    const startedAt = new Date().toISOString();
    const nextTitle =
      activeSession.messages.length <= 1 ? content.slice(0, 36) : activeSession.title;
    const readyUploads = pendingFiles.filter((item) => item.status === "ready");
    const uploadDataPath =
      readyUploads[0]?.savedPath?.replace(/[\\/][^\\/]+$/, "") ?? "";
    const ragIndexPath = uploadDataPath
      ? uploadDataPath.replace(/[\\/]uploads([\\/])/, "$1rag-index$1")
      : "";

    setDraft("");
    setHasStarted(true);
    setIsSending(true);

    updateSessionById(conversationId, (session) => ({
      ...session,
      title: nextTitle || session.title,
      updatedAt: startedAt,
      messages: [...session.messages, userMessage, assistantMessage],
      uploads: pendingFiles
    }));

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
          user_id: "web-user",
          metadata: {
            uploads: readyUploads,
            upload_data_path: uploadDataPath,
            rag_index_path: ragIndexPath,
            model: activeSession.model
          }
        })
      });

      if (!response.ok || !response.body) {
        const payload = (await response.json().catch(() => ({}))) as {
          reply?: string;
          error?: string;
        };
        throw new Error(
          payload.error ||
            payload.reply ||
            "The response channel is connected, but no reply was returned."
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const handleEvent = (eventType: string, payload: Record<string, unknown>) => {
        if (eventType === "delta") {
          appendAssistantContent(
            conversationId,
            assistantMessageId,
            String(payload.content ?? "")
          );
          return;
        }

        if (eventType === "done") {
          setAssistantMessage(conversationId, assistantMessageId, (message) => ({
            ...message,
            content:
              message.content || String(payload.reply ?? message.content ?? ""),
            isStreaming: false
          }));
          upsertThinkingStep(conversationId, assistantMessageId, {
            id: "stream-complete",
            kind: "status",
            title: "Answer complete",
            detail: "The full response has been streamed to the chat.",
            state: "done"
          });
          return;
        }

        if (eventType === "error") {
          const detail = String(payload.detail ?? "Failed to process message.");
          setAssistantMessage(conversationId, assistantMessageId, (message) => ({
            ...message,
            content: detail,
            isStreaming: false
          }));
          upsertThinkingStep(conversationId, assistantMessageId, {
            id: "stream-error",
            kind: "status",
            title: "Stream failed",
            detail,
            state: "error"
          });
          return;
        }

        if (eventType === "status") {
          upsertThinkingStep(conversationId, assistantMessageId, {
            id: String(payload.id ?? uid()),
            kind: "status",
            title: String(payload.title ?? "Status"),
            detail: String(payload.detail ?? ""),
            state:
              payload.state === "pending" ||
              payload.state === "done" ||
              payload.state === "error" ||
              payload.state === "info"
                ? payload.state
                : "info"
          });
          return;
        }

        if (eventType === "tool_call" || eventType === "tool_result") {
          upsertThinkingStep(conversationId, assistantMessageId, {
            id: String(payload.id ?? uid()),
            kind: "tool",
            title: String(
              payload.title ??
                payload.tool_name ??
                (eventType === "tool_call" ? "Calling tool" : "Tool result")
            ),
            detail: String(payload.detail ?? ""),
            state:
              payload.state === "pending" ||
              payload.state === "done" ||
              payload.state === "error" ||
              payload.state === "info"
                ? payload.state
                : eventType === "tool_call"
                  ? "pending"
                  : "done"
          });
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        while (buffer.includes("\n\n")) {
          const boundary = buffer.indexOf("\n\n");
          const rawEvent = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          const lines = rawEvent.split("\n");
          let eventType = "message";
          const dataLines: string[] = [];

          lines.forEach((line) => {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice(5).trim());
            }
          });

          if (dataLines.length === 0) {
            continue;
          }

          const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
          handleEvent(eventType, payload);
        }
      }

      setAssistantMessage(conversationId, assistantMessageId, (message) => ({
        ...message,
        isStreaming: false
      }));
    } catch (error) {
      const errorMessage =
        error instanceof Error && error.message.trim()
          ? error.message
          : "The UI is ready, but the API is not reachable yet. Start the Python API server and try again.";
      setAssistantMessage(conversationId, assistantMessageId, (message) => ({
        ...message,
        content: errorMessage,
        isStreaming: false
      }));
      upsertThinkingStep(conversationId, assistantMessageId, {
        id: "stream-unreachable",
        kind: "status",
        title: "Backend unavailable",
        detail: errorMessage,
        state: "error"
      });
    } finally {
      setIsSending(false);
    }
  };

  if (!activeSession) {
    return null;
  }

  return (
    <main className="flex min-h-screen bg-[var(--bg)] text-[var(--fg)] transition-colors duration-500">
      <Sidebar
        sidebarOpen={sidebarOpen}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onToggleSidebar={() => setSidebarOpen((current) => !current)}
        onCreateSession={createNewSession}
        onSelectSession={setActiveSessionId}
        onDeleteSession={deleteSession}
        formatTime={formatTime}
      />
      <ChatPanel
        activeSession={activeSession}
        hasStarted={hasStarted}
        isSending={isSending}
        draft={draft}
        pendingFiles={pendingFiles}
        models={MODELS}
        fileInputRef={fileInputRef}
        messageViewportRef={messageViewportRef}
        onDraftChange={setDraft}
        onFilePick={handleFilePick}
        onDropFiles={uploadFiles}
        onRemoveUpload={removeUpload}
        onSendMessage={sendMessage}
        onModelChange={(value) =>
          updateActiveSession((session) => ({
            ...session,
            model: value,
            updatedAt: new Date().toISOString()
          }))
        }
      />
    </main>
  );
}
