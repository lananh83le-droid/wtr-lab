import { useEffect, useState, useCallback } from "react";
import { FileText, ChevronLeft, ChevronRight, Copy, X } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { api, STATUS_META } from "@/lib/api";

const CH_LIMIT = 40;

const dot = { done: "bg-emerald-400", pending: "bg-slate-500", error: "bg-rose-400" };

export default function NovelDetailDrawer({ novel, open, onClose }) {
  const [data, setData] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(1);
  const [active, setActive] = useState(null);
  const [loadingCh, setLoadingCh] = useState(false);

  const load = useCallback(async () => {
    if (!novel) return;
    try { setData(await api.chapters(novel.id, { page, limit: CH_LIMIT })); } catch (e) {}
  }, [novel, page]);

  useEffect(() => { if (open) { setPage(1); setActive(null); } }, [open, novel]);
  useEffect(() => { if (open) load(); }, [open, load]);
  useEffect(() => { if (!open) return; const t = setInterval(load, 4000); return () => clearInterval(t); }, [open, load]);

  const openChapter = async (ch) => {
    if (ch.status !== "done") { toast.info("Chương này chưa được crawl xong"); return; }
    setLoadingCh(true);
    try { setActive(await api.chapter(ch.id)); }
    catch (e) { toast.error("Không tải được chương"); }
    finally { setLoadingCh(false); }
  };

  const copyText = () => {
    if (!active) return;
    navigator.clipboard.writeText(active.content || (active.body || []).join("\n"));
    toast.success("Đã sao chép nội dung gốc");
  };

  const totalPages = novel ? Math.max(1, Math.ceil(data.total / CH_LIMIT)) : 1;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-3xl bg-[#0a0e16] border-white/10 p-0 flex flex-col" data-testid="novel-detail-drawer">
        <SheetHeader className="px-5 py-4 border-b border-white/8">
          <SheetTitle className="text-slate-100 font-display flex items-center gap-2 pr-8">
            <FileText className="h-5 w-5 text-cyan-300" />
            <span className="truncate">{novel?.title_en || novel?.slug}</span>
          </SheetTitle>
          {novel && (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="font-cn text-rose-300/80">{novel.title_zh}</span>
              <span className={`px-2 py-0.5 rounded border ${(STATUS_META[novel.status] || STATUS_META.new).cls}`}>
                {(STATUS_META[novel.status] || STATUS_META.new).label}
              </span>
              <span className="mono">{novel.crawled_chapters}/{novel.total_chapters}</span>
            </div>
          )}
        </SheetHeader>

        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2">
          {/* chapter list */}
          <div className="border-r border-white/8 flex flex-col min-h-0">
            <div className="flex-1 overflow-auto p-2">
              {data.items.map((c) => (
                <button key={c.id} data-testid={`chapter-item-${c.chapter_order}`} onClick={() => openChapter(c)}
                  className={`w-full text-left px-3 py-2 rounded-md flex items-center gap-2.5 transition-colors ${active?.id === c.id ? "bg-cyan-400/12 border border-cyan-400/30" : "hover:bg-white/5 border border-transparent"}`}>
                  <span className={`h-2 w-2 rounded-full shrink-0 ${dot[c.status] || "bg-slate-500"}`} />
                  <span className="mono text-xs text-slate-500 w-10 shrink-0">#{c.chapter_order}</span>
                  <span className="text-xs text-slate-300 truncate">{c.title_en || c.title_zh || "—"}</span>
                </button>
              ))}
              {data.items.length === 0 && <div className="text-center text-slate-600 text-sm py-10">Chưa có chương nào.</div>}
            </div>
            <div className="flex items-center justify-between px-3 py-2 border-t border-white/8">
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} data-testid="ch-prev-btn">
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs mono text-slate-500">{page}/{totalPages}</span>
              <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} data-testid="ch-next-btn">
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* raw viewer */}
          <div className="flex flex-col min-h-0" data-testid="raw-viewer">
            {active ? (
              <>
                <div className="px-4 py-2.5 border-b border-white/8 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-cn text-rose-200 text-sm truncate">{active.title_zh_full || active.title_zh}</div>
                    <div className="text-[10px] text-slate-500 mono">{active.word_count} ký tự</div>
                  </div>
                  <Button size="sm" variant="outline" onClick={copyText} className="border-white/10 hover:bg-white/5 shrink-0" data-testid="copy-raw-btn">
                    <Copy className="h-3.5 w-3.5 mr-1" /> Chép
                  </Button>
                </div>
                <div className="flex-1 overflow-auto p-4 font-cn text-[15px] leading-loose text-rose-100/90 bg-black/30 space-y-3">
                  {(active.body || []).map((line, idx) => <p key={idx}>{line}</p>)}
                </div>
              </>
            ) : (
              <div className="flex-1 grid place-items-center text-slate-600 text-sm p-6 text-center">
                {loadingCh ? "Đang tải…" : "Chọn một chương (đã crawl xong) để xem nội dung gốc tiếng Trung."}
              </div>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
