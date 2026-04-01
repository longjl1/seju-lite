"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ChatPanel } from "./components/chat-panel";
import { Sidebar } from "./components/sidebar";
import { Message, Session } from "./types";

const MODELS = ["deepseek-chat", "gpt-4.1-mini", "gemini-2.0-flash"];
const STORAGE_KEY = "seju-lite-web-sessions";

const INTRO_MESSAGE =
  "seju.neo is a lightweight multi-agent runtime. Start with a task, a file, or a question and the workspace stays uncluttered.";

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
    messages: [
      {
        id: uid(),
        role: "assistant",
        content: INTRO_MESSAGE
      }
    ]
  };
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
  const [pendingFiles, setPendingFiles] = useState<string[]>([]);
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
          setSessions(parsed);
          setActiveSessionId(parsed[0].id);
          setHasStarted(parsed[0].messages.length > 1);
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

  const handleFilePick = (event: ChangeEvent<HTMLInputElement>) => {
    const names = Array.from(event.target.files ?? []).map((file) => file.name);
    if (names.length === 0) {
      return;
    }

    const nextUploads = [...pendingFiles, ...names];
    setPendingFiles(nextUploads);
    updateActiveSession((session) => ({
      ...session,
      uploads: nextUploads,
      updatedAt: new Date().toISOString()
    }));
    event.target.value = "";
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();

    const content = draft.trim();
    if (!content || !activeSession) {
      return;
    }

    const userMessage: Message = { id: uid(), role: "user", content };
    const conversationId = activeSession.id;
    const startedAt = new Date().toISOString();
    const nextTitle =
      activeSession.messages.length <= 1 ? content.slice(0, 36) : activeSession.title;

    setDraft("");
    setHasStarted(true);
    setIsSending(true);

    updateSessionById(conversationId, (session) => ({
      ...session,
      title: nextTitle || session.title,
      updatedAt: startedAt,
      messages: [...session.messages, userMessage],
      uploads: pendingFiles
    }));

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
          user_id: "web-user",
          metadata: {
            uploads: pendingFiles,
            model: activeSession.model
          }
        })
      });

      const payload = (await response.json()) as { reply?: string; error?: string };
      const assistantMessage: Message = {
        id: uid(),
        role: "assistant",
        content:
          payload.reply ||
          payload.error ||
          "The response channel is connected, but no reply was returned."
      };

      updateSessionById(conversationId, (session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        messages: [...session.messages, assistantMessage]
      }));
    } catch {
      const fallbackMessage: Message = {
        id: uid(),
        role: "assistant",
        content:
          "The UI is ready, but the API is not reachable yet. Start the Python API server and try again."
      };

      updateSessionById(conversationId, (session) => ({
        ...session,
        updatedAt: new Date().toISOString(),
        messages: [...session.messages, fallbackMessage]
      }));
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
