"use client";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Ellipsis, Trash2 } from "lucide-react";

import { Session } from "../types";

type SidebarProps = {
  sidebarOpen: boolean;
  sessions: Session[];
  activeSessionId: string;
  onToggleSidebar: () => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  formatTime: (value: string) => string;
};

export function Sidebar({
  sidebarOpen,
  sessions,
  activeSessionId,
  onToggleSidebar,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
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
            <p className="text-[0.68rem] uppercase tracking-[0.28em] text-[var(--app-muted)]">seju.neo</p>
            <p className="mt-1 text-sm">Chat sessions</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onToggleSidebar}
            aria-label={toggleLabel}
            title={toggleLabel}
            className="rounded-xl text-xs text-[var(--app-muted)] hover:bg-[var(--onhold)] hover:text-[var(--text)]"
          >
            <span className="sr-only">{toggleLabel}</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect
                x="0.75"
                y="0.75"
                width="14.5"
                height="14.5"
                rx="4.25"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <rect x="5" y="1" width="1.5" height="14" fill="currentColor" />
            </svg>
          </Button>
        </div>

        <div className="flex items-center gap-2 px-4 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onCreateSession}
            className="h-auto w-full justify-start rounded-xl px-3 py-2 text-left text-sm text-[var(--text)] hover:bg-[var(--onhold)] hover:text-[var(--text)]"
          >
            {sidebarOpen ? (
              <span className="flex items-center gap-2">
                <svg width="17" height="17" viewBox="0 0 17 17" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M15.565 0.686875C15.3484 0.46918 15.0909 0.296432 14.8073 0.178557C14.5237 0.0606809 14.2196 0 13.9125 0C13.6054 0 13.3013 0.0606809 13.0177 0.178557C12.7341 0.296432 12.4766 0.46918 12.26 0.686875L6.22375 6.72312C5.87183 7.0753 5.62211 7.5164 5.50125 7.99937L5.03375 9.87187C4.98726 10.0582 4.98978 10.2534 5.04108 10.4384C5.09238 10.6235 5.19071 10.7921 5.3265 10.9279C5.46228 11.0637 5.6309 11.162 5.81595 11.2133C6.001 11.2646 6.19618 11.2671 6.3825 11.2206L8.255 10.7531C8.73798 10.6323 9.17908 10.3825 9.53125 10.0306L15.5675 3.99437C16.48 3.08187 16.48 1.60187 15.5675 0.688125L15.565 0.686875ZM14.6812 3.10812L8.645 9.14437C8.45318 9.33603 8.213 9.4721 7.95 9.53812L6.3 9.95437L6.71375 8.30187C6.78 8.03937 6.915 7.79812 7.1075 7.60687L13.145 1.57062C13.2456 1.46911 13.3654 1.38853 13.4973 1.33355C13.6293 1.27856 13.7708 1.25025 13.9137 1.25025C14.0567 1.25025 14.1982 1.27856 14.3302 1.33355C14.4621 1.38853 14.5819 1.46911 14.6825 1.57062C14.7836 1.67162 14.8638 1.79156 14.9185 1.92357C14.9733 2.05559 15.0014 2.19709 15.0014 2.34C15.0014 2.48291 14.9733 2.62441 14.9185 2.75643C14.8638 2.88844 14.7836 3.00838 14.6825 3.10937L14.6812 3.10812ZM13.75 8.46187L15 7.21187V13.1269C15 14.8494 13.5987 16.2519 11.875 16.2519H3.125C2.2965 16.2509 1.50222 15.9213 0.916387 15.3355C0.330551 14.7497 0.000992411 13.9554 0 13.1269V4.37687C0 2.65437 1.40125 1.25187 3.125 1.25187H9.045L7.795 2.50187H3.125C2.09125 2.50187 1.25 3.34312 1.25 4.37687V13.1269C1.25 14.1606 2.09125 15.0019 3.125 15.0019H11.875C12.9088 15.0019 13.75 14.1606 13.75 13.1269V8.46187Z"
                    fill="currentColor"
                  />
                </svg>
                <span>New Chat</span>
              </span>
            ) : (
              "+"
            )}
          </Button>
        </div>

        <div className="thin-scrollbar flex-1 overflow-y-auto px-3 py-3">
          <div className="space-y-1">
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;

              return (
                <div
                  key={session.id}
                  className={`group flex items-start gap-1 rounded-2xl px-1 py-1 transition ${
                    isActive
                      ? "bg-[color-mix(in_srgb,var(--fg)_10%,transparent)]"
                      : "hover:bg-[color-mix(in_srgb,var(--fg)_6%,transparent)]"
                  }`}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => onSelectSession(session.id)}
                    className="h-auto flex-1 justify-start rounded-xl px-3 py-2 text-left text-[var(--text)] hover:bg-transparent"
                  >
                    <div className="flex min-w-0 flex-1 flex-col items-start">
                      <p className="truncate text-sm">
                        {sidebarOpen ? session.title : session.title.slice(0, 1)}
                      </p>
                      {sidebarOpen ? (
                        <div
                          className={`mt-1 flex w-full items-center justify-between text-[0.7rem] ${
                            isActive ? "text-[var(--text)]/70" : "text-[var(--app-muted)]"
                          }`}
                        >
                          <span className="truncate">{session.model}</span>
                          <span className="shrink-0">{formatTime(session.updatedAt)}</span>
                        </div>
                      ) : null}
                    </div>
                  </Button>

                  {sidebarOpen ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Session actions for ${session.title}`}
                            className="mt-1 shrink-0 rounded-xl text-[var(--app-muted)] hover:bg-[var(--onhold)] hover:text-[var(--text)]"
                          />
                        }
                      >
                        <Ellipsis className="size-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent
                        align="start"
                        side="bottom"
                        className="w-40 rounded-xl p-1 text-foreground shadow-lg backdrop-blur-md"
                      >
                      <DropdownMenuItem
                        onClick={() => onDeleteSession(session.id)}
                        className="rounded-lg text-[var(--app-muted)] transition-colors hover:bg-red-200 hover:text-red-500 focus:bg-[var(--onhold)]/70 focus:text-red-500 data-[highlighted]:text-red-500"
                      >
                        <Trash2 className="size-4 text-[var(--app-muted)] transition-colors group-data-[highlighted]/dropdown-menu-item:text-red-500" />
                        Delete
                      </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}
