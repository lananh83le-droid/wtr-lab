import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

const http = axios.create({ baseURL: API });

export const api = {
  stats: () => http.get("/stats").then((r) => r.data),
  crawlStatus: () => http.get("/crawl/status").then((r) => r.data),
  start: () => http.post("/crawl/start").then((r) => r.data),
  pause: () => http.post("/crawl/pause").then((r) => r.data),
  enumerate: (max_pages) => http.post("/crawl/enumerate", { max_pages }).then((r) => r.data),
  enumerateStop: () => http.post("/crawl/enumerate/stop").then((r) => r.data),

  novels: (params) => http.get("/novels", { params }).then((r) => r.data),
  addNovel: (url, priority = 0) => http.post("/novels/add", { url, priority }).then((r) => r.data),
  queueAll: (only_new = true) => http.post("/novels/queue-all", { only_new }).then((r) => r.data),
  novel: (id) => http.get(`/novels/${id}`).then((r) => r.data),
  queueNovel: (id, priority = 0) => http.post(`/novels/${id}/queue`, null, { params: { priority } }).then((r) => r.data),
  pauseNovel: (id) => http.post(`/novels/${id}/pause`).then((r) => r.data),
  retryNovel: (id) => http.post(`/novels/${id}/retry`).then((r) => r.data),
  deleteNovel: (id) => http.delete(`/novels/${id}`).then((r) => r.data),
  chapters: (id, params) => http.get(`/novels/${id}/chapters`, { params }).then((r) => r.data),
  chapter: (id) => http.get(`/chapters/${id}`).then((r) => r.data),
  exportUrl: (id, fmt) => `${API}/novels/${id}/export?fmt=${fmt}`,
  exportAllUrl: (fmt) => `${API}/export/all?fmt=${fmt}`,

  proxies: () => http.get("/proxies").then((r) => r.data),
  addProxy: (url, label) => http.post("/proxies", { url, label }).then((r) => r.data),
  deleteProxy: (id) => http.delete(`/proxies/${id}`).then((r) => r.data),
  toggleProxy: (id) => http.post(`/proxies/${id}/toggle`).then((r) => r.data),
  testProxy: (id) => http.post(`/proxies/${id}/test`).then((r) => r.data),

  logs: (params) => http.get("/logs", { params }).then((r) => r.data),
  clearLogs: () => http.delete("/logs").then((r) => r.data),

  settings: () => http.get("/settings").then((r) => r.data),
  saveSettings: (body) => http.put("/settings", body).then((r) => r.data),
};

export const STATUS_META = {
  new: { label: "Mới", cls: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
  queued: { label: "Trong hàng đợi", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  crawling: { label: "Đang crawl", cls: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" },
  done: { label: "Hoàn tất", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  partial: { label: "Một phần", cls: "bg-orange-500/15 text-orange-300 border-orange-500/30" },
  paused: { label: "Tạm dừng", cls: "bg-violet-500/15 text-violet-300 border-violet-500/30" },
  error: { label: "Lỗi", cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
};
