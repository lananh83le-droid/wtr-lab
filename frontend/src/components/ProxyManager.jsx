import { useEffect, useState } from "react";
import { Plus, Trash2, Zap, Server, CircleCheck, CircleX, CircleHelp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";

const STATUS_ICON = {
  alive: { icon: CircleCheck, cls: "text-emerald-400" },
  dead: { icon: CircleX, cls: "text-rose-400" },
  unknown: { icon: CircleHelp, cls: "text-slate-500" },
};

export default function ProxyManager() {
  const [proxies, setProxies] = useState([]);
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [testing, setTesting] = useState({});

  const load = async () => { try { setProxies(await api.proxies()); } catch (e) {} };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!url.trim()) return;
    try { await api.addProxy(url.trim(), label.trim()); toast.success("Đã thêm proxy"); setUrl(""); setLabel(""); load(); }
    catch (e) { toast.error("Không thể thêm proxy"); }
  };
  const del = async (id) => { await api.deleteProxy(id); toast.success("Đã xoá"); load(); };
  const toggle = async (id) => { await api.toggleProxy(id); load(); };
  const test = async (id) => {
    setTesting((t) => ({ ...t, [id]: true }));
    try { const r = await api.testProxy(id); toast[r.status === "alive" ? "success" : "error"](`Proxy ${r.status}${r.latency ? ` · ${r.latency}ms` : ""}`); load(); }
    catch (e) { toast.error("Test thất bại"); }
    finally { setTesting((t) => ({ ...t, [id]: false })); }
  };

  return (
    <div className="space-y-5" data-testid="proxies-tab">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight">Quản lý Proxy</h1>
        <p className="text-sm text-slate-400 mt-0.5">Xoay vòng IP để crawl nhanh và tránh bị chặn (Cloudflare Turnstile). Hỗ trợ HTTP/SOCKS5.</p>
      </div>

      <div className="card-surface rounded-xl p-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <Input data-testid="proxy-url-input" value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="http://user:pass@host:port  hoặc  socks5://host:port" className="bg-black/30 border-white/10 text-sm mono flex-1" />
          <Input data-testid="proxy-label-input" value={label} onChange={(e) => setLabel(e.target.value)}
            placeholder="Nhãn (tuỳ chọn)" className="bg-black/30 border-white/10 text-sm sm:w-44" />
          <Button data-testid="proxy-add-btn" onClick={add} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold">
            <Plus className="h-4 w-4 mr-1" /> Thêm
          </Button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Lưu ý: cần bật <b className="text-slate-300">"Dùng proxy"</b> trong tab Cấu hình để crawler sử dụng danh sách này.
        </p>
      </div>

      <div className="card-surface rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/5 text-[11px] uppercase tracking-wider text-slate-500 mono">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Bật</th>
              <th className="text-left px-3 py-3 font-medium">Proxy</th>
              <th className="text-left px-3 py-3 font-medium">Trạng thái</th>
              <th className="text-left px-3 py-3 font-medium">Độ trễ</th>
              <th className="text-right px-4 py-3 font-medium">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {proxies.length === 0 && <tr><td colSpan={5} className="text-center py-12 text-slate-500">Chưa có proxy nào.</td></tr>}
            {proxies.map((p, i) => {
              const S = STATUS_ICON[p.status] || STATUS_ICON.unknown;
              const Icon = S.icon;
              return (
                <tr key={p.id} data-testid={`proxy-row-${i}`} className="border-t border-white/5 hover:bg-white/[0.03]">
                  <td className="px-4 py-3"><Switch data-testid={`proxy-toggle-${i}`} checked={p.enabled} onCheckedChange={() => toggle(p.id)} /></td>
                  <td className="px-3 py-3">
                    <div className="mono text-xs text-slate-200 truncate max-w-[380px]">{p.url}</div>
                    {p.label && <div className="text-[11px] text-slate-500">{p.label}</div>}
                  </td>
                  <td className="px-3 py-3"><span className={`inline-flex items-center gap-1.5 text-xs ${S.cls}`}><Icon className="h-4 w-4" />{p.status}</span></td>
                  <td className="px-3 py-3 mono text-xs text-slate-400">{p.latency != null ? `${p.latency} ms` : "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button data-testid={`proxy-test-${i}`} size="sm" variant="outline" disabled={testing[p.id]}
                        onClick={() => test(p.id)} className="border-white/10 hover:bg-cyan-400/15 hover:text-cyan-200 h-8">
                        <Zap className="h-3.5 w-3.5 mr-1" />{testing[p.id] ? "…" : "Test"}
                      </Button>
                      <button data-testid={`proxy-delete-${i}`} onClick={() => del(p.id)} className="h-8 w-8 grid place-items-center rounded-md text-rose-300 hover:bg-rose-400/15">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
