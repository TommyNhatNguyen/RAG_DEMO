# Frontend API — Next.js handoff

Guide for a **Next.js App Router** UI against this repo’s FastAPI server. The backend is a **single-turn** e-learning RAG assistant: POST a question, stream the answer, show evidence with **Watch** / **Download** links.

Do **not** use the browser `EventSource` API. It is GET-only and cannot send a JSON body. Use `fetch` + `ReadableStream`.

Ingest is CLI-only (`python -m app.main ingest`). There is no upload/chat-history API.

---

## 1. Connect

### Backend

From the RAG repo root:

```bash
source .venv/bin/activate
python -m app.api
# listens on http://127.0.0.1:8000  (API_HOST / API_PORT)
```

| Check | Method | Path |
| --- | --- | --- |
| Liveness | `GET` | `/health` → `{ "status": "ok" }` |
| Index loaded | `GET` | `/v1/stats` |

The first `POST /v1/ask` can take tens of seconds (loads Qwen3-1.7B into RAM). Later asks reuse weights. **One generate at a time** (server lock). Disable Send while a stream is open.

### Recommended: same-origin proxy

`download_url` / `watch_url` / `preview_url` are **relative**, e.g. `/v1/files/assets/test/buoi_3.mp4#t=120,150`. They work as `<video src>` / `<a href>` only if the browser origin can fetch `/v1/...`.

In `next.config.ts`:

```ts
import type { NextConfig } from "next";

const API = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/health", destination: `${API}/health` },
      { source: "/v1/:path*", destination: `${API}/v1/:path*` },
    ];
  },
};

export default nextConfig;
```

Then the browser calls **same origin** (`""` or `window.location.origin`). No CORS. Media URLs work as returned.

`.env.local` (Next.js):

```bash
API_URL=http://127.0.0.1:8000
# only if you skip rewrites and call FastAPI directly:
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

`API_URL` is server-only (rewrites). `NEXT_PUBLIC_*` is inlined into the client — use it only for the “call FastAPI directly” path.

### Alternative: call FastAPI directly

Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`. FastAPI CORS defaults to `*` (`API_CORS_ORIGINS`). Prefix every relative file URL:

```ts
export function absUrl(path: string, apiBase: string) {
  if (!path) return path;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return new URL(path, apiBase.replace(/\/$/, "") + "/").toString();
}
```

With rewrites, `apiBase` is `""` and `absUrl("/v1/files/...", "")` can just return `path`.

### Auth

If the backend `.env` has `API_KEY` set, send header `X-API-Key` on:

- `GET /v1/stats`
- `POST /v1/search`
- `POST /v1/ask`

**Never** put the key on `/v1/files` or on `<video src>`. `<video>` cannot send custom headers. File routes are intentionally open (path-sandboxed).

Keep the key in a Next.js Route Handler if you must hide it from the browser; do not put `API_KEY` in `NEXT_PUBLIC_*`. Local PoC usually has `API_KEY` empty.

---

## 2. Endpoints

Base path prefix: `/v1` except `/health`.

### `GET /health`

```json
{ "status": "ok" }
```

Does not load the LLM. Does not require `X-API-Key`.

### `GET /v1/stats`

JSON: collection counts, `device`, `embedding`, `llm_model`. Use to confirm the index is non-empty (`text_count` / `visual_count`).

### `POST /v1/search`

Retrieval only (no LLM). Body:

```json
{
  "query": "quan hệ phản xạ",
  "k": 8,
  "text_only": true,
  "source": null
}
```

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `query` | string | required | Non-blank after trim; else **422** |
| `k` | int \| omit | server default | `1…50` |
| `text_only` | bool | **`true`** | `true` = skip visual collection (needed on 16GB Mac) |
| `source` | string \| omit | all files | filename (`buoi_3.mp4`) or repo path (`assets/test/buoi_3.mp4`) |

Response:

```ts
{ hits: Citation[]; assets: Asset[] }
```

### `POST /v1/ask`

Same body as search, plus:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `enhance` | bool \| omit | server `.env` | `true` = 1.7B JSON query planner before retrieve |
| `stream` | bool | **`true`** | `true` → SSE; `false` → one JSON body |

**Streaming (default):** `Content-Type: text/event-stream`.

**Non-stream:** `{ "answer", "citations", "assets", "query" }` where `query` is the planner or `null`.

Prefer `stream: true` for the chat UI. Keep `text_only: true` unless you know VL weights fit in RAM.

### `GET /v1/files/{path}`

Sandboxed file server. Allowed prefixes: `assets/…`, `storage/…`. Supports **HTTP Range** (required for `<video>` seek). `404` if outside those trees. `Content-Disposition: inline`.

Use `download_url` as-is for `<a download>`. Do not invent `file://` or `/Users/...` paths.

---

## 3. SSE protocol (`POST /v1/ask`, `stream: true`)

Each event:

```text
event: <name>
data: {…JSON…}

```

Keep-alive comments look like `: ping - …` — **ignore lines starting with `:`**.

`data` is always a JSON object (UTF-8). Chunks from `ReadableStream` can split mid-line; buffer until `\n`.

### Events (in order)

| `event` | When | `data` |
| --- | --- | --- |
| `status` | progress | `{ "stage": "enhancing" \| "retrieving" \| "generating" }` |
| `query` | after enhance | `{ "rewritten": string, "subqueries": string[], "step_back": string, "hyde": string }` — `hyde` is `""` unless `QUERY_HYDE` produced a paragraph; omitted if `enhance: false` |
| `sources` | **before tokens** | `{ "citations": Citation[], "assets": Asset[] }` |
| `delta` | tokens | `{ "text": string }` — already think-filtered; **concatenate** |
| `done` | finished | `{ "request_id": string }` |
| `error` | failure | `{ "message": string }` then stream ends |

`enhancing` is skipped when enhance is off. Empty index still streams an answer (model may say it lacks context); `assets` may be `[]`.

### Client state machine

```text
answer = ""
citations = []
assets = []
plan = null
stage = null

on status    → stage = data.stage          // spinner copy
on query     → plan = data                 // optional debug
on sources   → citations, assets = data     // render cards immediately
on delta     → answer += data.text          // typewriter
on done      → stop spinner
on error     → show data.message
```

HTTP **422** (empty query) happens **before** SSE. **401** if API key missing. Mid-stream failures are `event: error` with HTTP 200.

---

## 4. TypeScript types

```ts
export type AssetKind = "video" | "pdf" | "slide" | "image" | "document";
export type StatusStage = "enhancing" | "retrieving" | "generating";

export type Locator = {
  page: number | null;
  start_time: number | null;
  end_time: number | null;
  timestamp: number | null;
  label: string | null;
};

export type Citation = {
  id: string;
  index: number;
  content_type: string;
  score: number;
  title: string;
  snippet: string;
  locator: Locator;
  asset_id: string;
};

export type Asset = {
  id: string;
  kind: AssetKind;
  filename: string;
  media_type: string;
  download_url: string;
  watch_url: string;
  preview_url: string | null;
  locators: Locator[];
};

export type QueryPlan = {
  rewritten: string;
  subqueries: string[];
  step_back: string;
  hyde: string;
};

export type AskRequest = {
  query: string;
  k?: number;
  text_only?: boolean; // default true on server
  source?: string | null;
  course?: string | null;
  content_type?: string | null;
  enhance?: boolean | null;
  stream?: boolean; // default true
};

export type SearchRequest = {
  query: string;
  k?: number;
  text_only?: boolean;
  source?: string | null;
  course?: string | null;
  content_type?: string | null;
};

export type SearchResponse = { hits: Citation[]; assets: Asset[] };
export type AskJsonResponse = {
  answer: string;
  citations: Citation[];
  assets: Asset[];
  query: QueryPlan | null;
};
```

`Citation.asset_id` equals `Asset.id` (usually the course-relative path). Several citations can share one asset.

---

## 5. Next.js: consume the stream

Put this in a **client** module (`"use client"`). Do not parse SSE in a Server Component.

### SSE line parser

```ts
export type SseEvent = { event: string; data: unknown };

export async function* readSse(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let event = "message";

  const emitBlock = (block: string): SseEvent | null => {
    let name = event;
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    event = "message";
    if (!dataLines.length) return null;
    const raw = dataLines.join("\n");
    try {
      return { event: name, data: JSON.parse(raw) };
    } catch {
      return { event: name, data: raw };
    }
  };

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        const parsed = emitBlock(block.replaceAll("\r\n", "\n"));
        if (parsed) yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

### `askStream`

```ts
export async function askStream(
  body: AskRequest,
  opts: {
    apiBase?: string; // "" when using next.config rewrites
    apiKey?: string;
    signal?: AbortSignal;
    onEvent: (event: string, data: unknown) => void;
  },
) {
  const base = opts.apiBase ?? "";
  const res = await fetch(`${base}/v1/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(opts.apiKey ? { "X-API-Key": opts.apiKey } : {}),
    },
    body: JSON.stringify({ text_only: true, stream: true, ...body }),
    signal: opts.signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err));
  }
  if (!res.body) throw new Error("No response body");

  for await (const { event, data } of readSse(res.body, opts.signal)) {
    opts.onEvent(event, data);
  }
}
```

### Client component sketch

```tsx
"use client";

import { useRef, useState } from "react";
import { askStream } from "@/lib/rag";
import type { Asset, Citation, StatusStage } from "@/lib/rag-types";

export function AskForm() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [stage, setStage] = useState<StatusStage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setAnswer("");
    setAssets([]);
    setCitations([]);
    setError(null);
    setStreaming(true);
    setStage("retrieving");

    try {
      await askStream(
        { query, text_only: true },
        {
          signal: ac.signal,
          onEvent(event, data) {
            const d = data as Record<string, unknown>;
            if (event === "status") setStage(d.stage as StatusStage);
            if (event === "sources") {
              setCitations((d.citations as Citation[]) ?? []);
              setAssets((d.assets as Asset[]) ?? []);
            }
            if (event === "delta") setAnswer((prev) => prev + String(d.text ?? ""));
            if (event === "done") setStage(null);
            if (event === "error") {
              setError(String(d.message ?? "error"));
              setStage(null);
            }
          },
        },
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError((err as Error).message);
      setStage(null);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <textarea value={query} onChange={(e) => setQuery(e.target.value)} required />
      <button type="submit" disabled={streaming}>
        {stage ?? "Ask"}
      </button>
      {error && <p role="alert">{error}</p>}
      <article>{answer}</article>
    </form>
  );
}
```

Abort on unmount:

```ts
useEffect(() => () => abortRef.current?.abort(), []);
```

### Search (JSON)

```ts
const res = await fetch("/v1/search", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query, text_only: true }),
});
const { hits, assets }: SearchResponse = await res.json();
```

---

## 6. Render Watch / Download

`sources` (or search JSON) is enough to render cards **while** tokens still stream.

Resolve URLs with `absUrl(asset.watch_url, apiBase)` (`apiBase = ""` with rewrites).

| `kind` | Watch | Download |
| --- | --- | --- |
| `video` | `<video src={watch_url} controls preload="metadata" />` — `watch_url` already has `#t=START,END` (seconds) | `<a href={download_url} download={filename}>` |
| `pdf` | `<iframe src={watch_url} />` or `window.open` — `#page=N` | same file URL |
| `slide` | browser cannot play PPTX. Show `<img src={preview_url} />` if set; Watch can open the JPEG | `download_url` is the `.pptx` |
| `image` | `<img src={watch_url \|\| preview_url} />` | `download_url` |
| `document` | no in-browser viewer (DOCX/MD/TXT) | `download_url` only |

`asset.locators[]` are extra timestamps/pages for the same file. Build extra seek URLs:

- video: `${download_url}#t=${start},${end}`
- pdf: `${download_url}#page=${page}`

`locator.label` is a ready caption (`02:00–02:30`, `p.3`).

Inline citations: `citations` ordered by `index`. Link `[n]` to `assets.find(a => a.id === c.asset_id)`.

Example video card:

```tsx
function VideoCard({ asset, apiBase }: { asset: Asset; apiBase: string }) {
  const src = absUrl(asset.watch_url, apiBase);
  const dl = absUrl(asset.download_url, apiBase);
  return (
    <figure>
      <video src={src} controls playsInline />
      <figcaption>
        {asset.filename}
        {asset.locators[0]?.label ? ` · ${asset.locators[0].label}` : null}
      </figcaption>
      <a href={dl} download={asset.filename}>
        Download
      </a>
    </figure>
  );
}
```

---

## 7. UX constraints (do not skip)

- **Single-turn.** Each submit is a new question. Do not send chat history; the API ignores it.
- **One in-flight ask.** A second `POST /v1/ask` waits on the server lock (can look hung). Disable the button until `done` / `error` / abort.
- **Default `text_only: true`.** Setting `false` loads the 2B VL embedder on the same Mac and often OOMs.
- **First token latency.** Show `status.stage` (`enhancing` / `retrieving` / `generating`).
- **Index may be empty.** If `/v1/stats` `text_count` is 0, ingest on the backend first. The UI cannot ingest.
- **Vietnamese queries** are expected. Send NFC text as the user typed it.
- **No `EventSource`.** POST + `fetch` only.
- **Do not** proxy huge videos through a Next.js Route Handler unless necessary; `rewrites` streams Range from FastAPI.

---

## 8. Quick checklist

1. Backend: `python -m app.api` and `GET /health` → `ok`.
2. Next rewrites `/v1/:path*` → `http://127.0.0.1:8000/v1/:path*`.
3. Client form → `POST /v1/ask` with `{ query, text_only: true, stream: true }`.
4. Parse SSE; append `delta.text`; render `sources.assets`.
5. `<video src={watch_url}>` and `<a download href={download_url}>`.
6. AbortController on new submit / unmount.
