"use client";

import { Session } from "../types";

type SidebarProps = {
  sidebarOpen: boolean;
  sessions: Session[];
  activeSessionId: string;
  onToggleSidebar: () => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  formatTime: (value: string) => string;
};

export function Sidebar({
  sidebarOpen,
  sessions,
  activeSessionId,
  onToggleSidebar,
  onCreateSession,
  onSelectSession,
  formatTime
}: SidebarProps) {
  const toggleLabel = sidebarOpen ? "Collapse sidebar" : "Open sidebar";

  return (
    <aside
      className={`relative hidden border-r mono-border transition-all duration-500 ease-soft lg:flex ${
        sidebarOpen ? "w-[18rem]" : "w-[5.5rem]"
      }`}
    >
      <div className="flex h-screen w-full flex-col">
        <div
          className={`flex items-center border-b mono-border px-4 py-4 ${
            sidebarOpen ? "justify-between" : "justify-center"
          }`}
        >
          <div
            className={`transition-all duration-300 ${
              sidebarOpen ? "max-w-full opacity-100" : "max-w-0 overflow-hidden opacity-0"
            }`}
          >
            <p className="text-[0.68rem] uppercase tracking-[0.28em] text-[var(--muted)]">seju.neo</p>
            <p className="mt-1 text-sm">Chat sessions</p>
          </div>
          <button
            type="button"
            onClick={onToggleSidebar}
            aria-label={toggleLabel}
            title={toggleLabel}
            className="rounded-full border mono-border p-2 text-xs transition hover:bg-[var(--fg)] hover:text-[var(--bg)]"
          >
            <span className="sr-only">{toggleLabel}</span>
            <svg
              viewBox="-0.5 -0.5 16 16"
              aria-hidden="true"
              className={`h-4 w-4 transition-transform duration-300 ${
                sidebarOpen ? "rotate-0" : "rotate-180"
              }`}
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12.7769375 14.284625H2.2230625c-0.8326875 0 -1.5076875 -0.675 -1.5076875 -1.5076875l0 -10.553875c0 -0.8326875 0.675 -1.5076875 1.5076875 -1.5076875h10.553875c0.8326875 0 1.5076875 0.675 1.5076875 1.5076875v10.553875c0 0.8326875 -0.675 1.5076875 -1.5076875 1.5076875Z"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
              />
              <path
                d="M3.9192500000000003 5.9923125 2.6 7.5l1.3192499999999998 1.5076875"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
              />
              <path
                d="M5.615375 14.284625V0.7153750000000001"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
              />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-2 border-b mono-border px-4 py-3">
          <button
            type="button"
            onClick={onCreateSession}
            className="w-full rounded-full border mono-border px-3 py-2 text-sm transition hover:bg-[var(--fg)] hover:text-[var(--bg)]"
          >
            {sidebarOpen ? "New session" : "+"}
          </button>
        </div>

        <div className="thin-scrollbar flex-1 overflow-y-auto px-3 py-3">
          <div className="space-y-2">
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelectSession(session.id)}
                  className={`w-full rounded-3xl border px-3 py-3 text-left transition ${
                    isActive
                      ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--bg)]"
                      : "mono-border hover:border-[var(--fg)]"
                  }`}
                >
                  <p className="truncate text-sm">{sidebarOpen ? session.title : session.title.slice(0, 1)}</p>
                  {sidebarOpen ? (
                    <div
                      className={`mt-2 flex items-center justify-between text-[0.7rem] ${
                        isActive ? "text-[var(--bg)]/70" : "text-[var(--muted)]"
                      }`}
                    >
                      <span>{session.model}</span>
                      <span>{formatTime(session.updatedAt)}</span>
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}
