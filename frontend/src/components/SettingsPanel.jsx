import { useEffect, useState } from "react";
import { Save, Gauge, Timer, Server } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";

export default function SettingsPanel() {
  const [s, setS] = useState({ concurrency: 3, delay_ms: 300, use_proxy: false });

  useEffect(() => { api.settings().then(setS).catch(() => {}); }, []);

  const save = async () => {
    try {
      const saved = await api.saveSettings({
        concurrency: Number(s.concurrency), delay_ms: Number(s.delay_ms), use_proxy: !!s.use_proxy,
      });
      setS(saved);
      toast.success("Đã lưu cấu hình");
    } catch (e) { toast.error("Lưu thất bại"); }
  };

  return (
    <div className="space-y-5 max-w-2xl" data-testid="settings-tab">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight">Cấu hình Crawler</h1>
        <p className="text-sm text-slate-400 mt-0.5">Điều chỉnh tốc độ, độ trễ và proxy cho worker nền.</p>
      </div>

      <div className="card-surface rounded-xl p-5 space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Gauge className="h-4 w-4 text-cyan-300" />
            <label className="text-sm font-medium">Số luồng đồng thời (concurrency)</label>
            <span className="ml-auto mono text-cyan-300 text-sm">{s.concurrency}</span>
          </div>
          <Slider data-testid="concurrency-slider" value={[Number(s.concurrency)]} min={1} max={20} step={1}
            onValueChange={([v]) => setS({ ...s, concurrency: v })} />
          <p className="text-xs text-slate-500 mt-1.5">Cao hơn = nhanh hơn nhưng dễ bị Cloudflare chặn nếu không dùng proxy. Khuyến nghị 3 khi không proxy.</p>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Timer className="h-4 w-4 text-violet-300" />
            <label className="text-sm font-medium">Độ trễ giữa các request (ms)</label>
          </div>
          <Input data-testid="delay-input" type="number" value={s.delay_ms}
            onChange={(e) => setS({ ...s, delay_ms: e.target.value })}
            className="bg-black/30 border-white/10 mono w-40" />
        </div>

        <div className="flex items-center justify-between rounded-lg bg-black/30 border border-white/8 p-4">
          <div className="flex items-center gap-3">
            <Server className="h-4 w-4 text-emerald-300" />
            <div>
              <div className="text-sm font-medium">Dùng proxy</div>
              <div className="text-xs text-slate-500">Xoay vòng proxy đã bật ở tab Quản lý Proxy</div>
            </div>
          </div>
          <Switch data-testid="use-proxy-switch" checked={!!s.use_proxy} onCheckedChange={(v) => setS({ ...s, use_proxy: v })} />
        </div>

        <Button data-testid="save-settings-btn" onClick={save} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold">
          <Save className="h-4 w-4 mr-1.5" /> Lưu cấu hình
        </Button>
      </div>
    </div>
  );
}
