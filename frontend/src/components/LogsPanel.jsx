import { useEffect, useState, useCallback } from "react";
import { Trash2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";

const LEVEL_CLS = { ERROR: "text-rose-400", WARN: "text-amber-400", INFO: "text-emerald-400" };

export default function LogsPanel() {
  const [logs, setLogs] = useState([]);
  const [level, setLevel] = useState("all");

  const load = useCallback(async () => {
    try { setLogs(await api.logs({ limit: 300, level: level === "all" ? "" : level })); } catch (e) {}
  }, [level]);

  useEffect(() => { load(); const t = setInterval(load, 2500); return () => clearInterval(t); }, [load]);

  const clear = async () => { await api.clearLogs(); toast.success("Đã xoá nhật ký"); load(); };

  return (
    <div className="space-y-5" data-testid="logs-tab">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">Nhật ký & Lỗi</h1>
          <p className="text-sm text-slate-400 mt-0.5">Luồng sự kiện crawl realtime · {logs.length} dòng</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={level} onValueChange={setLevel}>
            <SelectTrigger data-testid="log-level-select" className="w-36 bg-black/30 border-white/10 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              <SelectItem value="INFO">INFO</SelectItem>
              <SelectItem value="WARN">WARN</SelectItem>
              <SelectItem value="ERROR">ERROR</SelectItem>
            </SelectContent>
          </Select>
          <Button data-testid="log-refresh-btn" size="sm" variant="outline" onClick={load} className="border-white/10 hover:bg-white/5">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button data-testid="log-clear-btn" size="sm" variant="outline" onClick={clear} className="border-white/10 hover:bg-rose-400/15 hover:text-rose-200">
            <Trash2 className="h-4 w-4 mr-1" /> Xoá
          </Button>
        </div>
      </div>

      <div className="card-surface rounded-xl p-4">
        <div className="rounded-lg bg-black/50 border border-white/5 p-4 h-[calc(100vh-260px)] overflow-auto mono text-xs space-y-1.5" data-testid="log-terminal">
          {logs.length === 0 && <div className="text-slate-600">Chưa có nhật ký…</div>}
          {logs.map((l) => (
            <div key={l.id} className="flex gap-2 hover:bg-white/[0.03] px-1 rounded">
              <span className="text-slate-600 shrink-0">{new Date(l.created_at).toLocaleTimeString()}</span>
              <span className={`${LEVEL_CLS[l.level] || "text-slate-400"} shrink-0 w-14`}>[{l.level}]</span>
              <span className="text-slate-300 break-all">{l.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
