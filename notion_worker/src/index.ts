import { WebhookVerificationError, Worker } from "@notionhq/workers";

declare const process: { env: Record<string, string | undefined> };
declare const Buffer: { from(value: string, encoding: "base64"): Uint8Array };

const worker = new Worker();
export default worker;

type ReportPayload = {
  report_id: string;
  report_url?: string;
  topic: string;
  depth?: "quick" | "deep";
  type?: "report" | "infographic" | "insight";
  context_text?: string;
  visuals?: boolean;
};

type RichText = {
  type: "text";
  text: { content: string; link?: { url: string } };
};

type NotionBlock = Record<string, unknown>;

const OPENAI_CHAT_COMPLETIONS = "https://api.openai.com/v1/chat/completions";
const OPENAI_IMAGES = "https://api.openai.com/v1/images/generations";

worker.webhook("buildLessonArtifact", {
  title: "Build Lesson Artifact",
  description: "Turns an Idea Companion report request into a finished Notion teaching workspace.",
  execute: async (events) => {
    for (const event of events) {
      verifyWorkerSecret(event.headers);
      const payload = parsePayload(event.body);
      await buildLessonArtifact(payload);
    }
  },
});

function verifyWorkerSecret(headers: Record<string, string>): void {
  const expected = process.env.IC_NOTION_WORKER_SECRET;
  if (!expected) {
    throw new WebhookVerificationError("IC_NOTION_WORKER_SECRET is not configured");
  }
  const actual = headers["x-ic-worker-secret"];
  if (!actual || actual !== expected) {
    throw new WebhookVerificationError("Invalid worker secret");
  }
}

function parsePayload(body: Record<string, unknown>): ReportPayload {
  const payload = body as Partial<ReportPayload>;
  if (!payload.report_id || !payload.topic) {
    throw new Error("Payload must include report_id and topic");
  }
  return {
    report_id: String(payload.report_id),
    report_url: payload.report_url ? String(payload.report_url) : undefined,
    topic: String(payload.topic).slice(0, 200),
    depth: payload.depth === "quick" ? "quick" : "deep",
    type: payload.type === "infographic" || payload.type === "insight" ? payload.type : "report",
    context_text: payload.context_text ? String(payload.context_text) : "",
    visuals: Boolean(payload.visuals),
  };
}

async function buildLessonArtifact(payload: ReportPayload): Promise<void> {
  await setStatus(payload.report_id, "In progress");
  try {
    const blocks = await buildBlocks(payload);
    const appended = await appendBlocks(payload.report_id, blocks);
    if (!appended) {
      await setStatus(payload.report_id, "Requested");
      await telegramPing(`I saved partial notes on "${payload.topic}" but the Notion Worker write was incomplete.`);
      return;
    }
    await setStatus(payload.report_id, "Ready");
    await telegramPing(`Ready: your Notion lesson on "${payload.topic}" is done.\n${payload.report_url ?? ""}`.trim());
  } catch (error) {
    console.error("[worker] build failed", error);
    await setStatus(payload.report_id, "Requested");
    await telegramPing(`I could not finish "${payload.topic}" this time. Ask me again and I will retry it.`);
    throw error;
  }
}

async function buildBlocks(payload: ReportPayload): Promise<NotionBlock[]> {
  if (payload.type === "insight") {
    return [
      ...learningArtifactHeader("Saved insight"),
      paragraph(payload.topic),
      divider(),
      heading2("Learning Record"),
      paragraph("This insight was important enough to save during a walk. Revisit it before the next related lesson."),
    ];
  }

  const markdown = await generateLessonMarkdown(payload);
  const blocks = [...learningArtifactHeader(payload.topic), ...markdownToBlocks(markdown)];

  if (payload.type === "infographic" || payload.visuals) {
    const imageId = await generateAndUploadImage(payload.topic);
    if (imageId) {
      blocks.splice(3, 0, imageBlock(imageId));
    } else {
      blocks.splice(3, 0, paragraph("Image generation was skipped or failed, but the lesson is ready to study."));
    }
  }

  return blocks;
}

function learningArtifactHeader(topic: string): NotionBlock[] {
  return [
    callout(
      "Created from a walking conversation. Notion is now the teaching workspace: mission, concepts, glossary, practice, quiz, and sources live here."
    ),
    paragraph(`Topic: ${topic}`),
    divider(),
  ];
}

async function generateLessonMarkdown(payload: ReportPayload): Promise<string> {
  const key = requireEnv("OPENAI_API_KEY");
  const model = process.env.IC_REPORT_MODEL ?? "gpt-4o-search-preview";
  const length =
    payload.depth === "deep" ? "a thorough but accessible teaching workspace" : "a concise teaching workspace";
  const system = [
    "You are a sharp tutor writing a follow-up Notion lesson for a smart builder and entrepreneur after a walking conversation.",
    "Search the web for current, accurate information when recency matters. Never invent figures or rely on stale memory.",
    "Write Markdown with this exact structure:",
    "# <topic>",
    "A one-line plain-English promise.",
    "## Mission Tie-In",
    "## 5-Bullet Summary",
    "## Explain It Like I Am Walking",
    "## Why This Matters",
    "## Concept Cards",
    "## Glossary Candidates",
    "## Practice Loop",
    "## Learning Record",
    "## Quiz Me Later",
    "## Trusted Resources",
    "## Next Action",
    "Use bullet lists, not Markdown tables. No emojis. No em dashes.",
  ].join("\n");
  let user = `Topic: ${payload.topic}\nLength: ${length}.\n`;
  if (payload.context_text) {
    user += `\nContext from the walk, for relevance only:\n${payload.context_text.slice(0, 1800)}\n`;
  }
  user += "\nWrite the Notion lesson now.";

  const requestBody: Record<string, unknown> = {
    model,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
  };
  if (!model.includes("search")) {
    requestBody.temperature = 0.6;
  }

  const response = await fetch(OPENAI_CHAT_COMPLETIONS, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });
  if (!response.ok) {
    throw new Error(`OpenAI report error ${response.status}: ${await response.text()}`);
  }
  const data = (await response.json()) as {
    choices: Array<{ message: { content?: string; annotations?: Array<Record<string, unknown>> } }>;
  };
  const message = data.choices[0]?.message;
  let text = noEmDash(message?.content ?? "");
  const sources = extractCitations(message?.annotations ?? []);
  if (sources.length > 0) {
    text += "\n\n## Sources\n" + sources.map((source) => `- [${source.title}](${source.url})`).join("\n");
  }
  return text;
}

function extractCitations(annotations: Array<Record<string, unknown>>): Array<{ title: string; url: string }> {
  const sources: Array<{ title: string; url: string }> = [];
  const seen = new Set<string>();
  for (const annotation of annotations) {
    const citation = annotation.url_citation as { title?: string; url?: string } | undefined;
    if (citation?.url && !seen.has(citation.url)) {
      seen.add(citation.url);
      sources.push({ title: citation.title ?? citation.url, url: citation.url });
    }
  }
  return sources.slice(0, 8);
}

async function generateAndUploadImage(topic: string): Promise<string | null> {
  const key = requireEnv("OPENAI_API_KEY");
  const prompt =
    `A clean, friendly educational diagram for "${topic}". Use simple labels, soft colors, minimal text, and no watermark.`;
  const response = await fetch(OPENAI_IMAGES, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: process.env.IC_IMAGE_MODEL ?? "gpt-image-1",
      prompt: prompt.slice(0, 900),
      size: "1024x1024",
    }),
  });
  if (!response.ok) {
    console.error("[worker] image failed", response.status, await response.text());
    return null;
  }
  const data = (await response.json()) as { data: Array<{ b64_json: string }> };
  const bytes = Buffer.from(data.data[0]?.b64_json ?? "", "base64");
  if (bytes.length === 0) {
    return null;
  }
  return uploadImage(bytes);
}

async function uploadImage(bytes: Uint8Array): Promise<string | null> {
  const token = requireEnv("NOTION_API_TOKEN");
  const fileVersion = process.env.NOTION_FILE_VERSION ?? "2026-03-11";
  const create = await fetch("https://api.notion.com/v1/file_uploads", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Notion-Version": fileVersion,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ filename: "lesson-diagram.png", content_type: "image/png" }),
  });
  if (!create.ok) {
    console.error("[worker] file upload create failed", create.status, await create.text());
    return null;
  }
  const upload = (await create.json()) as { id: string };
  const form = new FormData();
  form.append("file", new Blob([bytes], { type: "image/png" }), "lesson-diagram.png");
  const send = await fetch(`https://api.notion.com/v1/file_uploads/${upload.id}/send`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Notion-Version": fileVersion,
    },
    body: form,
  });
  if (!send.ok) {
    console.error("[worker] file upload send failed", send.status, await send.text());
    return null;
  }
  return upload.id;
}

async function setStatus(pageId: string, status: string): Promise<void> {
  await notionPatch(`/v1/pages/${pageId}`, {
    properties: {
      Status: { select: { name: status } },
    },
  });
}

async function appendBlocks(pageId: string, blocks: NotionBlock[]): Promise<boolean> {
  let ok = true;
  for (let index = 0; index < blocks.length; index += 90) {
    const response = await notionPatch(`/v1/blocks/${pageId}/children`, { children: blocks.slice(index, index + 90) });
    if (!response.ok) {
      ok = false;
      console.error("[worker] append failed", response.status, await response.text());
    }
  }
  return ok;
}

async function notionPatch(path: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(`https://api.notion.com${path}`, {
    method: "PATCH",
    headers: notionHeaders(process.env.NOTION_VERSION ?? "2022-06-28"),
    body: JSON.stringify(body),
  });
}

function notionHeaders(version: string): Record<string, string> {
  return {
    Authorization: `Bearer ${requireEnv("NOTION_API_TOKEN")}`,
    "Notion-Version": version,
    "Content-Type": "application/json",
  };
}

async function telegramPing(text: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.IC_OWNER_CHAT_ID;
  if (!token || !chatId) {
    return;
  }
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

function markdownToBlocks(markdown: string): NotionBlock[] {
  const blocks: NotionBlock[] = [];
  for (const raw of markdown.split("\n")) {
    const line = raw.trim();
    if (!line) {
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push(heading3(line.slice(4)));
    } else if (line.startsWith("## ")) {
      blocks.push(heading2(line.slice(3)));
    } else if (line.startsWith("# ")) {
      blocks.push(heading1(line.slice(2)));
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      blocks.push(bullet(line.slice(2)));
    } else if (/^\d+[.)]\s+/.test(line)) {
      blocks.push(numbered(line.replace(/^\d+[.)]\s+/, "")));
    } else {
      blocks.push(paragraph(line));
    }
  }
  return blocks.slice(0, 180);
}

function richText(text: string): RichText[] {
  const parts: RichText[] = [];
  const normalized = text.replace(/\*\*/g, "");
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  let position = 0;
  for (const match of normalized.matchAll(pattern)) {
    if (match.index > position) {
      parts.push({ type: "text", text: { content: normalized.slice(position, match.index).slice(0, 1900) } });
    }
    parts.push({ type: "text", text: { content: match[1].slice(0, 1900), link: { url: match[2] } } });
    position = match.index + match[0].length;
  }
  if (position < normalized.length) {
    parts.push({ type: "text", text: { content: normalized.slice(position).slice(0, 1900) } });
  }
  return parts.length ? parts : [{ type: "text", text: { content: "" } }];
}

function paragraph(text: string): NotionBlock {
  return { object: "block", type: "paragraph", paragraph: { rich_text: richText(text) } };
}

function heading1(text: string): NotionBlock {
  return { object: "block", type: "heading_1", heading_1: { rich_text: richText(text) } };
}

function heading2(text: string): NotionBlock {
  return { object: "block", type: "heading_2", heading_2: { rich_text: richText(text) } };
}

function heading3(text: string): NotionBlock {
  return { object: "block", type: "heading_3", heading_3: { rich_text: richText(text) } };
}

function bullet(text: string): NotionBlock {
  return { object: "block", type: "bulleted_list_item", bulleted_list_item: { rich_text: richText(text) } };
}

function numbered(text: string): NotionBlock {
  return { object: "block", type: "numbered_list_item", numbered_list_item: { rich_text: richText(text) } };
}

function callout(text: string): NotionBlock {
  return {
    object: "block",
    type: "callout",
    callout: {
      rich_text: [{ type: "text", text: { content: text.slice(0, 1900) } }],
      icon: { type: "emoji", emoji: "🧠" },
    },
  };
}

function divider(): NotionBlock {
  return { object: "block", type: "divider", divider: {} };
}

function imageBlock(fileUploadId: string): NotionBlock {
  return {
    object: "block",
    type: "image",
    image: { type: "file_upload", file_upload: { id: fileUploadId } },
  };
}

function noEmDash(value: string): string {
  return value.replace(/[—―]/g, ", ").replace(/–/g, "-");
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not configured`);
  }
  return value;
}
