// Empty string = same-origin relative requests (e.g. "/api/predict/"), which is what
// the production nginx container needs since it proxies /api/ to the backend service
// (see webapp/frontend/nginx.conf) - works from any host/IP with no rebuild required.
// Local `npm run dev` (no nginx in front) sets VITE_API_BASE=http://localhost:8000 via .env.
const API_BASE = import.meta.env.VITE_API_BASE || "";

// DRF validation errors look like {"models": ["..."], "text": ["..."]}; turn
// them into one readable line instead of raw JSON.
function errorMessage(data, status) {
  if (data.error) return data.error;
  const parts = Object.entries(data).map(([field, msgs]) =>
    `${field}: ${Array.isArray(msgs) ? msgs.join(" ") : String(msgs)}`
  );
  return parts.join(" | ") || `Request failed (${status})`;
}

async function parseJsonOrThrow(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.quota = data.quota ?? null; // present on 429 (out of credits)
    throw error;
  }
  return data;
}

function postJson(path, body) {
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(parseJsonOrThrow);
}

// Only the models passed in are run (and charged) by the backend.
export function predictText(text, models) {
  return postJson("/api/predict/", { text, models });
}

// Word-importance explanation for the given models (SVM, LSTM, BERT only).
export function explainText(text, models) {
  return postJson("/api/predict/explain/", { text, models });
}

// Returns { models: [...], limits: { max_text_chars, batch_max_rows } }.
export async function fetchModels() {
  const response = await fetch(`${API_BASE}/api/models/`);
  return parseJsonOrThrow(response);
}

// { enabled: false } locally; otherwise limit/remaining/reset_in_seconds/...
export async function fetchQuota() {
  const response = await fetch(`${API_BASE}/api/quota/`);
  return parseJsonOrThrow(response);
}

export async function predictBatch(file, models) {
  const formData = new FormData();
  formData.append("file", file);
  models.forEach((key) => formData.append("models", key));
  const response = await fetch(`${API_BASE}/api/predict/batch/`, {
    method: "POST",
    body: formData,
  });
  return parseJsonOrThrow(response);
}

function csvEscape(value) {
  const str = String(value ?? "");
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function buildCsvBlob(lines) {
  const csv = ["text", ...lines.map(csvEscape)].join("\n");
  return new Blob([csv], { type: "text/csv" });
}

export function mapBatchRowsToSummary(data) {
  return data.rows.map((row) => ({
    id: row.row_index,
    label: row.text_preview,
    text: row.text,
    results: row.results,
  }));
}

export function downloadCsv(filename, rows, models) {
  const header = ["row", "text", ...models.map((m) => `${m.key}_prediction`)];
  const lines = rows.map((row) =>
    [row.id, row.text ?? row.label, ...models.map((m) => row.results[m.key]?.predicted_label ?? "")]
      .map(csvEscape)
      .join(",")
  );
  const csv = [header.join(","), ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
