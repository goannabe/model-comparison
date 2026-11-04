// Empty string = same-origin relative requests (e.g. "/api/predict/"), which is what
// the production nginx container needs since it proxies /api/ to the backend service
// (see webapp/frontend/nginx.conf) - works from any host/IP with no rebuild required.
// Local `npm run dev` (no nginx in front) sets VITE_API_BASE=http://localhost:8000 via .env.
const API_BASE = import.meta.env.VITE_API_BASE || "";

async function parseJsonOrThrow(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || JSON.stringify(data) || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

export async function predictText(text) {
  const response = await fetch(`${API_BASE}/api/predict/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return parseJsonOrThrow(response);
}

export async function predictExplain(text) {
  const response = await fetch(`${API_BASE}/api/predict/explain/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return parseJsonOrThrow(response);
}

export async function predictWithExplanation(text) {
  const [prediction, explanation] = await Promise.all([predictText(text), predictExplain(text)]);
  const results = Object.fromEntries(
    Object.entries(prediction.results).map(([modelKey, result]) => [
      modelKey,
      { ...result, tokens: explanation.results[modelKey]?.tokens ?? [] },
    ])
  );
  return { ...prediction, results };
}

export async function fetchModels() {
  const response = await fetch(`${API_BASE}/api/models/`);
  const data = await parseJsonOrThrow(response);
  return data.models;
}

export async function predictBatch(file) {
  const formData = new FormData();
  formData.append("file", file);
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
