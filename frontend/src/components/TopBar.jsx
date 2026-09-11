import { Play, Pause, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function TopBar({ status, stats, onChange }) {
  const toggle = async () => {
    try {
      if (status.running) {
        await api.pause();
        toast.info("Đã tạm dừng crawler");
      } else {
        await api.start();
        toast.success("Đã khởi động crawler");
      }
      onChange();
    } catch (e) {
      toast.error("Thao tác thất bại");
    }
  };

  return (
    <header className="h-16 shrink-0 border-b border-white/8 bg-[#0a0e16]/60 backdrop-blur-xl px-6 flex items-center justify-between gap-4" data-testid="topbar">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Wifi className="h-4 w-4 text-emerald-400" />
          <span className="mono text-xs">wtr-lab.com</span>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 pulse-dot" />
        </div>
        <div className="hidden lg:flex items-center gap-4 pl-4 ml-2 border-l border-white/10 text-xs text-slate-500 mono">
          <span>Truyện: <b className="text-slate-200">{stats.total_novels ?? 0}</b></span>
          <span>Chương: <b className="text-slate-200">{stats.total_chapters ?? 0}</b></span>
          <span>Hàng đợi: <b className="text-amber-300">{stats.queue_size ?? 0}</b></span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs mono text-slate-400">
          <span className={`h-2 w-2 rounded-full ${status.running ? "bg-emerald-400 pulse-dot" : "bg-slate-600"}`} />
          {status.running ? "RUNNING" : "IDLE"}
        </div>
        <Button
          data-testid="global-toggle-btn"
          onClick={toggle}
          className={
            status.running
              ? "bg-rose-500/15 text-rose-200 border border-rose-500/40 hover:bg-rose-500/25 hover:text-rose-100"
              : "bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold shadow-[0_0_22px_-6px_rgba(0,240,255,0.8)]"
          }
        >
          {status.running ? <><Pause className="h-4 w-4 mr-1.5" /> Tạm dừng</> : <><Play className="h-4 w-4 mr-1.5" /> Bắt đầu</>}
        </Button>
      </div>
    </header>
  );
}
