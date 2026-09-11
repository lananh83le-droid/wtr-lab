import { useEffect, useState, useCallback } from "react";
import { Play, Pause, RotateCcw, Trash2, Eye, FileDown, Plus, Layers, Search, ChevronLeft, ChevronRight, Archive, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import { api, API, STATUS_META } from "@/lib/api";
import NovelDetailDrawer from "@/components/NovelDetailDrawer";

const LIMIT = 12;

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.new;
  return <span className={`text-[11px] px-2 py-0.5 rounded border whitespace-nowrap ${m.cls}`}>{m.label}</span>;
}

export default function NovelsTable({ status, onChange }) {
  const [data, setData] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [url, setUrl] = useState("");
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.novels({
        page, limit: LIMIT, search,
        status: filter === "all" ? "" : filter,
      });
      setData(res);
    } catch (e) {}
  }, [page, search, filter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 3500); return () => clearInterval(t); }, [load]);

  const addNovel = async () => {
    if (!url.trim()) return;
    try {
      await api.addNovel(url.trim(), 10);
      toast.success("Đã thêm truyện vào hàng đợi và bắt đầu crawl");
      setUrl(""); load(); onChange();
    } catch (e) { toast.error(e?.response?.data?.detail || "URL không hợp lệ"); }
  };

  const act = async (fn, msg) => {
    try { await fn(); toast.success(msg); load(); onChange(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Thất bại"); }
  };

  const download = (id, fmt) => { window.open(api.exportUrl(id, fmt), "_blank"); };
  const downloadAll = (fmt) => {
    toast.info(`Đang tạo file ZIP (.${fmt}) cho toàn bộ kho truyện…`);
    window.open(api.exportAllUrl(fmt), "_blank");
  };

  const totalPages = Math.max(1, Math.ceil(data.total / LIMIT));

  return (
    <div className="space-y-5" data-testid="novels-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Danh sách Truyện</h1>
          <p className="text-sm text-slate-400 mt-0.5">{data.total} truyện · trang {page}/{totalPages}</p>
        </div>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button data-testid="export-all-btn" className="bg-emerald-500/90 hover:bg-emerald-500 text-white font-medium">
                <Archive className="h-4 w-4 mr-1.5" /> Xuất toàn bộ (.zip) <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-[#0f1523] border-white/10">
              <DropdownMenuItem data-testid="export-all-txt" onClick={() => downloadAll("txt")} className="cursor-pointer">
                <FileDown className="h-4 w-4 mr-2 text-emerald-300" /> ZIP các file .TXT
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="export-all-json" onClick={() => downloadAll("json")} className="cursor-pointer">
                <Layers className="h-4 w-4 mr-2 text-sky-300" /> ZIP các file .JSON
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button data-testid="queue-all-btn" onClick={() => act(() => api.queueAll(true), "Đã xếp hàng tất cả truyện 'Mới'")}
            className="bg-violet-500/90 hover:bg-violet-500 text-white font-medium">
            <Layers className="h-4 w-4 mr-1.5" /> Xếp hàng tất cả (Mới)
          </Button>
        </div>
      </div>

      {/* add + filters */}
      <div className="card-surface rounded-xl p-4 space-y-3">
        <div className="flex gap-2">
          <Input data-testid="add-novel-input" value={url} onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addNovel()}
            placeholder="Dán URL truyện, vd: https://wtr-lab.com/en/novel/1439/become-a-master-from-hokage"
            className="bg-black/30 border-white/10 text-sm" />
          <Button data-testid="add-novel-btn" onClick={addNovel} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold shrink-0">
            <Plus className="h-4 w-4 mr-1" /> Thêm & Crawl
          </Button>
        </div>
        <div className="flex gap-2 items-center">
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input data-testid="novel-search-input" value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Tìm theo tên hoặc slug…" className="pl-9 bg-black/30 border-white/10 text-sm" />
          </div>
          <Select value={filter} onValueChange={(v) => { setFilter(v); setPage(1); }}>
            <SelectTrigger data-testid="novel-filter-select" className="w-44 bg-black/30 border-white/10 text-sm">
              <SelectValue placeholder="Trạng thái" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả trạng thái</SelectItem>
              {Object.keys(STATUS_META).map((k) => <SelectItem key={k} value={k}>{STATUS_META[k].label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* table */}
      <div className="card-surface rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-[11px] uppercase tracking-wider text-slate-500 mono">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Truyện</th>
                <th className="text-left px-3 py-3 font-medium hidden lg:table-cell">Tác giả</th>
                <th className="text-left px-3 py-3 font-medium w-[220px]">Tiến độ</th>
                <th className="text-left px-3 py-3 font-medium">Trạng thái</th>
                <th className="text-right px-4 py-3 font-medium">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 && (
                <tr><td colSpan={5} className="text-center py-14 text-slate-500">
                  Chưa có truyện. Dán URL ở trên hoặc dùng "Quét Tất Cả" ở Tổng quan.
                </td></tr>
              )}
              {data.items.map((n, i) => {
                const pct = n.total_chapters ? Math.round((n.crawled_chapters / n.total_chapters) * 100) : 0;
                return (
                  <tr key={n.id} data-testid={`novel-row-${i}`} className="border-t border-white/5 hover:bg-white/[0.03] transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        {n.cover ? (
                          <img src={n.cover} alt="" className="h-12 w-9 rounded object-cover border border-white/10 shrink-0" />
                        ) : <div className="h-12 w-9 rounded bg-white/5 border border-white/10 shrink-0" />}
                        <div className="min-w-0">
                          <div className="font-medium text-slate-100 truncate max-w-[320px]">{n.title_en || n.slug}</div>
                          <div className="font-cn text-rose-300/80 text-xs truncate max-w-[320px]">{n.title_zh || "—"}</div>
                          <div className="text-[10px] text-slate-600 mono">#{n.source_id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-slate-400 hidden lg:table-cell max-w-[140px] truncate">{n.author || "—"}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center justify-between text-xs mono text-slate-400 mb-1">
                        <span>{n.crawled_chapters}/{n.total_chapters || "?"}</span><span>{pct}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-white/8 overflow-hidden">
                        <div className={`h-full rounded-full ${n.status === "crawling" ? "progress-crawl" : "bg-emerald-400/80"}`} style={{ width: `${pct}%` }} />
                      </div>
                    </td>
                    <td className="px-3 py-3"><StatusBadge status={n.status} /></td>
                    <td className="px-4 py-3">
                      <TooltipProvider delayDuration={100}>
                        <div className="flex items-center justify-end gap-1">
                          <IconBtn testid={`view-btn-${i}`} tip="Xem chương" onClick={() => setDetail(n)} icon={Eye} />
                          {["new", "paused", "partial", "error", "done"].includes(n.status) && (
                            <IconBtn testid={`start-btn-${i}`} tip="Crawl" onClick={() => act(() => api.queueNovel(n.id, 10), "Đã xếp hàng")} icon={Play} tone="text-cyan-300 hover:bg-cyan-400/15" />
                          )}
                          {["queued", "crawling"].includes(n.status) && (
                            <IconBtn testid={`pause-btn-${i}`} tip="Tạm dừng" onClick={() => act(() => api.pauseNovel(n.id), "Đã tạm dừng truyện")} icon={Pause} tone="text-violet-300 hover:bg-violet-400/15" />
                          )}
                          <IconBtn testid={`retry-btn-${i}`} tip="Thử lại lỗi" onClick={() => act(() => api.retryNovel(n.id), "Đã đưa lại vào hàng đợi")} icon={RotateCcw} tone="text-amber-300 hover:bg-amber-400/15" />
                          <IconBtn testid={`export-txt-btn-${i}`} tip="Xuất .TXT" onClick={() => download(n.id, "txt")} icon={FileDown} tone="text-emerald-300 hover:bg-emerald-400/15" />
                          <IconBtn testid={`export-json-btn-${i}`} tip="Xuất .JSON" onClick={() => download(n.id, "json")} icon={Layers} tone="text-sky-300 hover:bg-sky-400/15" />
                          <IconBtn testid={`delete-btn-${i}`} tip="Xoá" onClick={() => act(() => api.deleteNovel(n.id), "Đã xoá truyện")} icon={Trash2} tone="text-rose-300 hover:bg-rose-400/15" />
                        </div>
                      </TooltipProvider>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-4 py-3 border-t border-white/5">
          <span className="text-xs text-slate-500 mono">Tổng {data.total}</span>
          <div className="flex items-center gap-2">
            <Button data-testid="prev-page-btn" size="sm" variant="outline" disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))} className="border-white/10 hover:bg-white/5 disabled:opacity-40">
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs mono text-slate-400">{page} / {totalPages}</span>
            <Button data-testid="next-page-btn" size="sm" variant="outline" disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="border-white/10 hover:bg-white/5 disabled:opacity-40">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <NovelDetailDrawer novel={detail} open={!!detail} onClose={() => setDetail(null)} />
    </div>
  );
}

function IconBtn({ testid, tip, onClick, icon: Icon, tone = "text-slate-300 hover:bg-white/10" }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button data-testid={testid} onClick={onClick} className={`h-8 w-8 grid place-items-center rounded-md transition-colors ${tone}`}>
          <Icon className="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent><span className="text-xs">{tip}</span></TooltipContent>
    </Tooltip>
  );
}
