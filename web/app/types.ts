export type Role = "assistant" | "user" | "system";

export type Message = {
  id: string;
  role: Role;
  content: string;
};

export type Session = {
  id: string;
  title: string;
  model: string;
  updatedAt: string;
  messages: Message[];
  uploads: string[];
};
