import { useState } from "react";
import { Sparkles, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const fmt = (iso) => (iso ? new Date(iso).toLocaleString("vi-VN") : "—");

export default function AutoScanCard({ status, settings, onChange }) {
  const [busy, setBusy] = useState(false);
  const a = status.auto_scan || {};
  const enabled = !!settings?.auto_scan_enabled;

  const scanNow = async () => {
    setBusy(true);
    try {
      await api.scanNew(null);
      toast.success("Bắt đầu quét truyện mới");
      onChange?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Không thể quét"); }
    finally { setBusy(false); }
  };

  return (
    <div className="card-surface rounded-xl p-5" data-testid="auto-scan-card">
      <div className="flex flex-col lg:flex-row lg:items-center gap-4 justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-emerald-400/12 border border-emerald-400/30 grid place-items-center">
            <Sparkles className={`h-5 w-5 text-emerald-300 ${a.running ? "animate-pulse" : ""}`} />
          </div>
          <div>
            <div className="font-display font-semibold flex items-center gap-2">
              Tự động quét truyện mới
              <span data-testid="auto-scan-status-badge" className={`text-[10px] px-2 py-0.5 rounded border mono ${
                a.running ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40"
                : enabled ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                : "bg-slate-500/15 text-slate-400 border-slate-500/30"}`}>
                {a.running ? `ĐANG QUÉT ${a.page}/${a.pages}` : enabled ? "ĐANG BẬT" : "TẮT"}
              </span>
            </div>
            <div className="text-xs text-slate-400 mono" data-testid="auto-scan-info">
              Lần cuối: {fmt(a.last_run)} · Kế tiếp: {enabled ? fmt(a.next_run) : "—"} · Mới: {a.last_found ?? 0} (tổng {a.total_found ?? 0})
            </div>
          </div>
        </div>
        <Button data-testid="scan-new-now-btn" onClick={scanNow} disabled={busy || a.running}
          className="bg-emerald-400 text-slate-950 hover:bg-emerald-300 font-semibold">
          <RefreshCw className={`h-4 w-4 mr-1.5 ${a.running ? "animate-spin" : ""}`} /> Quét truyện mới ngay
        </Button>
      </div>
    </div>
  );
}
