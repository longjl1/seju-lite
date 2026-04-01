import { mkdir, readdir, rm, writeFile } from "fs/promises";
import path from "path";

import { NextRequest, NextResponse } from "next/server";

function workspaceRoot() {
  return path.resolve(process.cwd(), "..", "workspace");
}

function sanitizeSegment(value: string) {
  return value.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function sanitizeFilename(name: string) {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_");
}

function sessionUploadRoot(conversationId: string) {
  return path.join(workspaceRoot(), "uploads", sanitizeSegment(conversationId));
}

function sessionRagIndexRoot(conversationId: string) {
  return path.join(workspaceRoot(), "rag-index", sanitizeSegment(conversationId));
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const conversationId = String(formData.get("conversation_id") || "").trim();
  const file = formData.get("file");

  if (!conversationId) {
    return NextResponse.json({ error: "Missing conversation_id." }, { status: 400 });
  }

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Missing file." }, { status: 400 });
  }

  const safeConversationId = sanitizeSegment(conversationId);
  const uploadRoot = sessionUploadRoot(safeConversationId);
  const uniqueName = `${crypto.randomUUID()}-${sanitizeFilename(file.name)}`;
  const savedPath = path.join(uploadRoot, uniqueName);

  await mkdir(uploadRoot, { recursive: true });
  const buffer = Buffer.from(await file.arrayBuffer());
  await writeFile(savedPath, buffer);

  return NextResponse.json({
    file: {
      id: uniqueName,
      name: file.name,
      savedPath,
      relativePath: path.relative(path.resolve(process.cwd(), ".."), savedPath),
      size: file.size,
      status: "ready"
    }
  });
}

export async function DELETE(request: NextRequest) {
  const body = (await request.json()) as {
    conversation_id?: string;
    upload_id?: string;
  };

  const conversationId = String(body.conversation_id || "").trim();
  const uploadId = String(body.upload_id || "").trim();

  if (!conversationId || !uploadId) {
    return NextResponse.json({ error: "Missing conversation_id or upload_id." }, { status: 400 });
  }

  const safeConversationId = sanitizeSegment(conversationId);
  const safeUploadId = sanitizeFilename(uploadId);
  const savedPath = path.join(sessionUploadRoot(safeConversationId), safeUploadId);

  await rm(savedPath, { force: true });
  const remaining = await readdir(sessionUploadRoot(safeConversationId)).catch(() => []);
  if (remaining.length === 0) {
    await rm(sessionRagIndexRoot(safeConversationId), { recursive: true, force: true });
  }
  return NextResponse.json({ ok: true });
}
