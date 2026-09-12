import { useEffect, useState } from "react";
import { BookMarked, FileText, Gauge, ListOrdered, Server, TriangleAlert, Search, Radar, StopCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { api, STATUS_META } from "@/lib/api";
import AutoScanCard from "@/components/AutoScanCard";

const Stat = ({ icon: Icon, label, value, tone, testid }) => (
  <div className="card-surface rounded-xl p-4 relative overflow-hidden" data-testid={testid}>
    <div className={`absolute top-0 left-0 right-0 h-[2px] ${tone}`} />
    <div className="flex items-center justify-between">
      <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mono">{label}</span>
      <Icon className="h-4 w-4 text-slate-500" />
    </div>
    <div className="mono text-2xl font-semibold mt-3 text-slate-100">{value}</div>
  </div>
);

export default function Dashboard({ stats, status, onChange, setTab }) {
  const [logs, setLogs] = useState([]);
  const [pages, setPages] = useState("");
  const [settings, setSettings] = useState(null);
  const en = status.enumerate || {};

  const loadLogs = async () => {
    try { setLogs(await api.logs({ limit: 8 })); } catch (e) {}
  };
  useEffect(() => { loadLogs(); const t = setInterval(loadLogs, 3000); return () => clearInterval(t); }, []);
  useEffect(() => { api.settings().then(setSettings).catch(() => {}); }, [status.auto_scan?.last_run]);

  const runEnumerate = async () => {
    try {
      await api.enumerate(pages ? parseInt(pages) : null);
      toast.success(pages ? `Bắt đầu quét ${pages} trang danh sách` : "Bắt đầu quét TOÀN BỘ website (94k+ truyện)");
      onChange();
    } catch (e) { toast.error(e?.response?.data?.detail || "Không thể quét"); }
  };
  const stopEnumerate = async () => { await api.enumerateStop(); toast.info("Đã dừng quét"); onChange(); };

  const byStatus = stats.novels_by_status || {};
  const enumPct = en.pages ? Math.round((en.page / en.pages) * 100) : 0;

  return (
    <div className="space-y-6" data-testid="dashboard">
      <div>
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">Trung tâm điều khiển Crawl</h1>
        <p className="text-sm text-slate-400 mt-1">Thu thập truyện gốc tiếng Trung từ wtr-lab.com và lưu vào MongoDB.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <Stat testid="stat-novels" icon={BookMarked} label="Tổng truyện" value={stats.total_novels ?? 0} tone="bg-cyan-400" />
        <Stat testid="stat-chapters" icon={FileText} label="Chương đã crawl" value={stats.chapters_done ?? 0} tone="bg-emerald-400" />
        <Stat testid="stat-total-chapters" icon={ListOrdered} label="Tổng chương" value={stats.total_chapters ?? 0} tone="bg-sky-400" />
        <Stat testid="stat-throughput" icon={Gauge} label="Tốc độ /phút" value={stats.throughput ?? 0} tone="bg-violet-400" />
        <Stat testid="stat-queue" icon={Server} label="Hàng đợi" value={stats.queue_size ?? 0} tone="bg-amber-400" />
        <Stat testid="stat-errors" icon={TriangleAlert} label="Lỗi" value={stats.chapters_error ?? 0} tone="bg-rose-400" />
      </div>

      {/* Enumerate bar */}
      <div className="card-surface rounded-xl p-5" data-testid="enumerate-bar">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4 justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-cyan-400/12 border border-cyan-400/30 grid place-items-center">
              <Radar className={`h-5 w-5 text-cyan-300 ${en.running ? "animate-spin" : ""}`} />
            </div>
            <div>
              <div className="font-display font-semibold">Quét danh sách truyện</div>
              <div className="text-xs text-slate-400">Liệt kê toàn bộ catalog wtr-lab.com vào hàng đợi (10 truyện / trang)</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Input
              data-testid="enumerate-pages-input"
              value={pages}
              onChange={(e) => setPages(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="Số trang (trống = tất cả)"
              className="w-48 bg-black/30 border-white/10 mono text-sm"
            />
            {en.running ? (
              <Button data-testid="enumerate-stop-btn" onClick={stopEnumerate} className="bg-rose-500/15 text-rose-200 border border-rose-500/40 hover:bg-rose-500/25">
                <StopCircle className="h-4 w-4 mr-1.5" /> Dừng
              </Button>
            ) : (
              <Button data-testid="enumerate-btn" onClick={runEnumerate} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold">
                <Search className="h-4 w-4 mr-1.5" /> Quét Tất Cả
              </Button>
            )}
          </div>
        </div>
        {(en.running || en.done) && (
          <div className="mt-4">
            <div className="flex justify-between text-xs mono text-slate-400 mb-1.5">
              <span>Trang {en.page}/{en.pages || "?"} · phát hiện {en.discovered} / {en.total} truyện</span>
              <span>{enumPct}%</span>
            </div>
            <Progress value={enumPct} className="h-2 bg-white/5" />
          </div>
        )}
      </div>

      <AutoScanCard status={status} settings={settings} onChange={onChange} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* status breakdown */}
        <div className="card-surface rounded-xl p-5">
          <div className="font-display font-semibold mb-4">Phân bố trạng thái</div>
          <div className="space-y-2.5">
            {Object.keys(STATUS_META).map((k) => (
              <div key={k} className="flex items-center justify-between">
                <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_META[k].cls}`}>{STATUS_META[k].label}</span>
                <span className="mono text-sm text-slate-200">{byStatus[k] || 0}</span>
              </div>
            ))}
          </div>
          <Button data-testid="goto-novels-btn" onClick={() => setTab("novels")} variant="outline" className="w-full mt-4 border-white/10 hover:bg-white/5 hover:text-cyan-200">
            Mở danh sách truyện
          </Button>
        </div>

        {/* mini log terminal */}
        <div className="card-surface rounded-xl p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="font-display font-semibold">Nhật ký gần đây</div>
            <button className="text-xs text-cyan-300 hover:text-cyan-200" onClick={() => setTab("logs")} data-testid="goto-logs-btn">Xem tất cả →</button>
          </div>
          <div className="rounded-lg bg-black/40 border border-white/5 p-3 h-[260px] overflow-auto mono text-xs space-y-1.5">
            {logs.length === 0 && <div className="text-slate-600">Chưa có nhật ký…</div>}
            {logs.map((l) => (
              <div key={l.id} className="flex gap-2">
                <span className={
                  l.level === "ERROR" ? "text-rose-400" : l.level === "WARN" ? "text-amber-400" : "text-emerald-400"
                }>[{l.level}]</span>
                <span className="text-slate-500 shrink-0">{new Date(l.created_at).toLocaleTimeString()}</span>
                <span className="text-slate-300">{l.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
