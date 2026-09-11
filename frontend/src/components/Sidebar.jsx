import { LayoutDashboard, BookMarked, Server, Terminal, Settings2, Database, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { id: "dashboard", label: "Tổng quan", icon: LayoutDashboard },
  { id: "novels", label: "Danh sách Truyện", icon: BookMarked },
  { id: "proxies", label: "Quản lý Proxy", icon: Server },
  { id: "logs", label: "Nhật ký Lỗi", icon: Terminal },
  { id: "settings", label: "Cấu hình", icon: Settings2 },
];

export default function Sidebar({ tab, setTab, stats, status }) {
  return (
    <aside className="w-[240px] shrink-0 border-r border-white/8 bg-[#0a0e16]/80 backdrop-blur-xl hidden md:flex flex-col" data-testid="sidebar">
      <div className="px-5 py-5 border-b border-white/8">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-lg bg-cyan-400/15 border border-cyan-400/40 grid place-items-center">
            <Database className="h-5 w-5 text-cyan-300" />
          </div>
          <div>
            <div className="font-display font-bold text-[15px] leading-tight tracking-tight">WTR-Crawler</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mono">wtr-lab.com</div>
          </div>
        </div>
      </div>

      <div className="px-3 py-4 flex-1">
        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-600 px-3 mb-2 mono">Điều hướng</div>
        <nav className="space-y-1">
          {NAV.map((n) => {
            const Icon = n.icon;
            const active = tab === n.id;
            return (
              <button
                key={n.id}
                data-testid={`nav-${n.id}`}
                onClick={() => setTab(n.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200",
                  active
                    ? "bg-cyan-400/12 text-cyan-200 border border-cyan-400/30 shadow-[0_0_18px_-8px_rgba(0,240,255,0.6)]"
                    : "text-slate-400 hover:text-slate-100 hover:bg-white/5 border border-transparent"
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="font-medium">{n.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-3 border-t border-white/8 space-y-3">
        <div className="card-surface rounded-lg p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase tracking-widest text-slate-500 mono">Trạng thái</span>
            <span className={cn("h-2 w-2 rounded-full", status.running ? "bg-emerald-400 pulse-dot" : "bg-slate-600")} />
          </div>
          <div className="font-display font-semibold text-sm">
            {status.running ? "Đang chạy" : "Đã dừng"}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-center">
            <div className="rounded-md bg-black/30 py-1.5">
              <div className="mono text-cyan-300 text-sm font-semibold">{status.active ?? 0}</div>
              <div className="text-[9px] text-slate-500 uppercase">Luồng</div>
            </div>
            <div className="rounded-md bg-black/30 py-1.5">
              <div className="mono text-emerald-300 text-sm font-semibold">{status.throughput ?? 0}</div>
              <div className="text-[9px] text-slate-500 uppercase">ch/phút</div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 px-2 text-[11px] text-slate-500">
          <Activity className="h-3.5 w-3.5 text-emerald-400" /> MongoDB đã kết nối
        </div>
      </div>
    </aside>
  );
}
