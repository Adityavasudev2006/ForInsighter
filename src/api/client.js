const BASE = "http://localhost:8000/api";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, options);
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Network error";
    throw new Error(
      `Request blocked (${reason}). Ensure backend is running on http://localhost:8000 and CORS allows your frontend origin (localhost/127.0.0.1).`,
    );
  }
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        const body = await response.json();
        const detail = body?.detail || body?.message || JSON.stringify(body);
        throw new Error(`${detail} (HTTP ${response.status})`);
      } catch {
        throw new Error(`Request failed (${response.status})`);
      }
    }
    const body = await response.text();
    throw new Error((body || `Request failed (${response.status})`).trim());
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.blob();
}

export async function uploadFiles(files, config = { mode: "local" }) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const params = new URLSearchParams();
  params.set("mode", config.mode || "local");
  if (config.apiProvider) params.set("api_provider", config.apiProvider);
  if (config.apiKey) params.set("api_key", config.apiKey);
  if (config.ollamaBaseUrl) params.set("ollama_base_url", config.ollamaBaseUrl);
  if (config.ollamaModel) params.set("ollama_model", config.ollamaModel);
  return request(`/documents/upload?${params.toString()}`, { method: "POST", body: formData });
}

export async function uploadLink(url, config = { mode: "local" }) {
  const params = new URLSearchParams();
  params.set("mode", config.mode || "local");
  if (config.apiProvider) params.set("api_provider", config.apiProvider);
  if (config.apiKey) params.set("api_key", config.apiKey);
  if (config.ollamaBaseUrl) params.set("ollama_base_url", config.ollamaBaseUrl);
  if (config.ollamaModel) params.set("ollama_model", config.ollamaModel);
  return request(`/documents/upload-link?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export const getDocuments = () => request("/documents");
export const getDocument = (id) => request(`/documents/${id}`);
export const deleteDocument = (id) => request(`/documents/${id}`, { method: "DELETE" });
export const summarize = (id, mode, config = {}) => {
  const params = new URLSearchParams();
  params.set("mode", mode);
  if (config.apiProvider) params.set("api_provider", config.apiProvider);
  if (config.apiKey) params.set("api_key", config.apiKey);
  if (config.ollamaBaseUrl) params.set("ollama_base_url", config.ollamaBaseUrl);
  if (config.ollamaModel) params.set("ollama_model", config.ollamaModel);
  return request(`/analysis/${id}/summarize?${params.toString()}`, { method: "POST" });
};
export const compareModels = (id, config = {}) => {
  const params = new URLSearchParams();
  if (config.apiProvider) params.set("api_provider", config.apiProvider);
  if (config.apiKey) params.set("api_key", config.apiKey);
  if (config.ollamaBaseUrl) params.set("ollama_base_url", config.ollamaBaseUrl);
  if (config.ollamaModel) params.set("ollama_model", config.ollamaModel);
  const query = params.toString();
  return request(`/analysis/${id}/compare${query ? `?${query}` : ""}`, { method: "POST" });
};
export const getQuestions = (id) => request(`/analysis/${id}/questions`);
export const getEntities = (id) => request(`/analysis/${id}/entities`);
export const getCharts = (id) => request(`/analysis/${id}/charts`);
export const chat = (id, message, history, mode = "local", config = {}) => {
  const params = new URLSearchParams();
  params.set("mode", mode);
  if (config.apiProvider) params.set("api_provider", config.apiProvider);
  if (config.apiKey) params.set("api_key", config.apiKey);
  if (config.ollamaBaseUrl) params.set("ollama_base_url", config.ollamaBaseUrl);
  if (config.ollamaModel) params.set("ollama_model", config.ollamaModel);
  return request(`/chat/${id}?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
};
export const getChatHistory = (id) => request(`/chat/${id}/history`);
export const clearChat = (id) => request(`/chat/${id}/history`, { method: "DELETE" });
export const search = (query, docIds = []) =>
  request("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, doc_ids: docIds }),
  });
export const startBatch = (docIds) =>
  request("/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_ids: docIds }),
  });
export const getBatchStatus = (taskId) => request(`/batch/${taskId}`);
export const validateLLM = (config = {}) =>
  request("/llm/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: config.mode || "local",
      api_provider: config.apiProvider,
      api_key: config.apiKey,
      ollama_base_url: config.ollamaBaseUrl,
      ollama_model: config.ollamaModel,
    }),
  });

export async function exportDoc(id, format) {
  const res = await fetch(`${BASE}/export/${id}?format=${format}`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  // Allow backend-provided filename when present (especially for PDF).
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename=\"?([^\";]+)\"?/i);
  link.download = (m && m[1]) || `${id}.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}
