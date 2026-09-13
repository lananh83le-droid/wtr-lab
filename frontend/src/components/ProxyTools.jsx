import { useState } from "react";
import { Download, ClipboardPaste, RefreshCw, Trash2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

const Pill = ({ label, value, cls, testid }) => (
  <div className={`rounded-lg border px-3 py-2 ${cls}`} data-testid={testid}>
    <div className="text-[10px] uppercase tracking-[0.16em] mono opacity-70">{label}</div>
    <div className="mono text-lg font-semibold">{value}</div>
  </div>
);

export default function ProxyTools({ summary, onChange }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const h = summary.harvest || {};

  const run = async (fn, okMsg) => {
    setBusy(true);
    try { const r = await fn(); toast.success(typeof okMsg === "function" ? okMsg(r) : okMsg); onChange(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Thao tác thất bại"); }
    finally { setBusy(false); }
  };

  const bulk = () => {
    if (!text.trim()) return;
    run(() => api.bulkProxies(text), (r) => `Đã thêm ${r.added} proxy, bỏ qua ${r.skipped} trùng`).then(() => setText(""));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      <div className="card-surface rounded-xl p-4 lg:col-span-3 space-y-3" data-testid="proxy-bulk-card">
        <div className="flex items-center gap-2">
          <ClipboardPaste className="h-4 w-4 text-cyan-300" />
          <div className="font-display font-semibold text-sm">Nhập nhiều proxy cùng lúc</div>
          <span className="text-xs text-slate-500 ml-auto mono">{text.split(/\n/).filter((l) => l.trim()).length} dòng</span>
        </div>
        <Textarea data-testid="proxy-bulk-textarea" value={text} onChange={(e) => setText(e.target.value)} rows={5}
          placeholder={"Mỗi dòng 1 proxy:\n1.2.3.4:8080\nuser:pass@1.2.3.4:3128\nsocks5://1.2.3.4:1080\n1.2.3.4:8080:user:pass"}
          className="bg-black/30 border-white/10 mono text-xs resize-none" />
        <div className="flex items-center gap-2">
          <Button data-testid="proxy-bulk-add-btn" onClick={bulk} disabled={busy || !text.trim()}
            className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold">
            <Download className="h-4 w-4 mr-1.5" /> Thêm hàng loạt
          </Button>
          <span className="text-xs text-slate-500">Tự bỏ trùng · mặc định http:// nếu không ghi giao thức</span>
        </div>
      </div>

      <div className="card-surface rounded-xl p-4 lg:col-span-2 space-y-3" data-testid="proxy-harvest-card">
        <div className="flex items-center gap-2">
          <Wand2 className={`h-4 w-4 text-emerald-300 ${h.running ? "animate-pulse" : ""}`} />
          <div className="font-display font-semibold text-sm">Tự động lấy proxy miễn phí</div>
        </div>
        <p className="text-xs text-slate-500">Tải HTTP + SOCKS5 từ {h.sources || 70}+ nguồn công khai (TheSpeedX, proxifly, monosans, jetkai, yakumo…), test trực tiếp với wtr-lab.com, chỉ giữ proxy sống. Đã chạy {h.runs || 0} lượt.</p>
        <div className="grid grid-cols-4 gap-2">
          <Pill testid="proxy-pill-total" label="Tổng" value={summary.total ?? 0} cls="border-white/10 bg-black/30 text-slate-200" />
          <Pill testid="proxy-pill-alive" label="Sống" value={summary.alive ?? 0} cls="border-emerald-500/30 bg-emerald-500/10 text-emerald-300" />
          <Pill testid="proxy-pill-available" label="Sẵn sàng" value={summary.available ?? 0} cls="border-cyan-500/30 bg-cyan-500/10 text-cyan-300" />
          <Pill testid="proxy-pill-dead" label="Chết" value={summary.dead ?? 0} cls="border-rose-500/30 bg-rose-500/10 text-rose-300" />
        </div>
        {h.running && (
          <div data-testid="proxy-harvest-progress">
            <div className="flex justify-between text-xs mono text-slate-400 mb-1">
              <span>{h.phase === "fetch" ? `Tầng ${h.tier}: đang tải danh sách…` : `Tầng ${h.tier} · đã test ${h.tested}/${h.fetched} · sống ${h.alive}`}</span>
              <span>+{h.added}</span>
            </div>
            <Progress value={h.fetched ? (h.tested / h.fetched) * 100 : 5} className="h-1.5 bg-white/5" />
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button data-testid="proxy-harvest-btn" onClick={() => run(() => api.harvestProxies(null), "Bắt đầu thu thập proxy")}
            disabled={busy || h.running} className="bg-emerald-400 text-slate-950 hover:bg-emerald-300 font-semibold">
            <Wand2 className="h-4 w-4 mr-1.5" /> {h.running ? "Đang thu thập…" : "Tự động lấy proxy"}
          </Button>
          <Button data-testid="proxy-recheck-btn" variant="outline" disabled={busy}
            onClick={() => run(() => api.recheckProxies(), "Đang kiểm tra lại toàn bộ proxy")}
            className="border-white/10 hover:bg-white/5 hover:text-cyan-200">
            <RefreshCw className="h-4 w-4 mr-1.5" /> Kiểm tra lại
          </Button>
          <Button data-testid="proxy-purge-dead-btn" variant="outline" disabled={busy || !summary.dead}
            onClick={() => run(() => api.purgeDeadProxies(), (r) => `Đã xoá ${r.deleted} proxy chết`)}
            className="border-rose-500/30 text-rose-300 hover:bg-rose-500/10">
            <Trash2 className="h-4 w-4 mr-1.5" /> Xoá proxy chết
          </Button>
        </div>
      </div>
    </div>
  );
}
