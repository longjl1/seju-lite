export type Role = "assistant" | "user" | "system";

export type ThinkingStep = {
  id: string;
  kind: "status" | "tool";
  title: string;
  detail?: string;
  state: "pending" | "done" | "error" | "info";
};

export type Message = {
  id: string;
  role: Role;
  content: string;
  isStreaming?: boolean;
  thinkingSteps?: ThinkingStep[];
};

export type UploadedDocument = {
  id: string;
  name: string;
  savedPath?: string;
  relativePath?: string;
  size?: number;
  status: "uploading" | "ready" | "error";
  error?: string;
  indexedAt?: string;
};

export type Session = {
  id: string;
  title: string;
  model: string;
  updatedAt: string;
  messages: Message[];
  uploads: UploadedDocument[];
};
