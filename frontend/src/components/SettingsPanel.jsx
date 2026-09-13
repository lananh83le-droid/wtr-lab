import { useEffect, useState } from "react";
import { Save, Gauge, Timer, Server, Sparkles, Layers, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";

export default function SettingsPanel() {
  const [s, setS] = useState({
    concurrency: 3, delay_ms: 300, use_proxy: false,
    auto_scan_enabled: false, auto_scan_interval_min: 60, auto_scan_pages: 3, chapter_limit: 0,
    parallel_novels: 1, proxy_auto_harvest: true, proxy_max_pool: 400, auto_queue_new: true,
  });

  useEffect(() => { api.settings().then(setS).catch(() => {}); }, []);

  const save = async () => {
    try {
      const saved = await api.saveSettings({
        concurrency: Number(s.concurrency), delay_ms: Number(s.delay_ms), use_proxy: !!s.use_proxy,
        auto_scan_enabled: !!s.auto_scan_enabled,
        auto_scan_interval_min: Math.max(5, Number(s.auto_scan_interval_min) || 60),
        auto_scan_pages: Math.max(1, Number(s.auto_scan_pages) || 3),
        chapter_limit: Math.max(0, Number(s.chapter_limit) || 0),
        parallel_novels: Math.min(30, Math.max(1, Number(s.parallel_novels) || 1)),
        proxy_auto_harvest: !!s.proxy_auto_harvest, auto_queue_new: !!s.auto_queue_new,
        proxy_max_pool: Math.max(10, Number(s.proxy_max_pool) || 200),
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
          <Slider data-testid="concurrency-slider" value={[Number(s.concurrency)]} min={1} max={100} step={1}
            onValueChange={([v]) => setS({ ...s, concurrency: v })} />
          <p className="text-xs text-slate-500 mt-1.5">Số chương tải song song trong 1 truyện. Không proxy: nên để 3. Có proxy pool: 20–50.</p>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Layers className="h-4 w-4 text-amber-300" />
            <label className="text-sm font-medium">Số truyện crawl song song</label>
            <span className="ml-auto mono text-amber-300 text-sm">{s.parallel_novels}</span>
          </div>
          <Slider data-testid="parallel-novels-slider" value={[Number(s.parallel_novels) || 1]} min={1} max={30} step={1}
            onValueChange={([v]) => setS({ ...s, parallel_novels: v })} />
          <p className="text-xs text-slate-500 mt-1.5">Tổng request đồng thời ≈ số truyện × số luồng. Chỉ nên tăng khi đã có proxy pool.</p>
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

        <div className="rounded-lg bg-black/30 border border-white/8 p-4 space-y-4" data-testid="proxy-auto-settings">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Wand2 className="h-4 w-4 text-emerald-300" />
              <div>
                <div className="text-sm font-medium">Tự động duy trì pool proxy</div>
                <div className="text-xs text-slate-500">Liên tục: thu thập proxy miễn phí khi pool thiếu, kiểm tra lại mỗi 10 phút, tự tắt proxy chết, tự xếp lại truyện còn chương chờ</div>
              </div>
            </div>
            <Switch data-testid="proxy-auto-harvest-switch" checked={!!s.proxy_auto_harvest}
              onCheckedChange={(v) => setS({ ...s, proxy_auto_harvest: v })} />
          </div>
          <div>
            <label className="text-xs text-slate-400">Số proxy sống tối đa trong pool</label>
            <Input data-testid="proxy-max-pool-input" type="number" min={10} value={s.proxy_max_pool}
              onChange={(e) => setS({ ...s, proxy_max_pool: e.target.value })}
              className="bg-black/30 border-white/10 mono mt-1 w-40" />
          </div>
        </div>

        <div className="rounded-lg bg-black/30 border border-white/8 p-4 space-y-4" data-testid="auto-scan-settings">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Layers className="h-4 w-4 text-cyan-300" />
              <div>
                <div className="text-sm font-medium">Tự động nạp hàng đợi</div>
                <div className="text-xs text-slate-500">Khi hàng đợi trống: xếp lại truyện còn chương chờ, rồi tự đưa truyện "Mới" (chưa crawl) vào hàng đợi</div>
              </div>
            </div>
            <Switch data-testid="auto-queue-new-switch" checked={!!s.auto_queue_new}
              onCheckedChange={(v) => setS({ ...s, auto_queue_new: v })} />
          </div>
          <div className="h-px bg-white/8" />
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles className="h-4 w-4 text-emerald-300" />
              <div>
                <div className="text-sm font-medium">Tự động quét truyện mới</div>
                <div className="text-xs text-slate-500">Định kỳ kiểm tra các trang đầu danh sách, tự thêm & crawl truyện chưa có trong kho</div>
              </div>
            </div>
            <Switch data-testid="auto-scan-switch" checked={!!s.auto_scan_enabled}
              onCheckedChange={(v) => setS({ ...s, auto_scan_enabled: v })} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400">Chu kỳ quét (phút)</label>
              <Input data-testid="auto-scan-interval-input" type="number" min={5} value={s.auto_scan_interval_min}
                onChange={(e) => setS({ ...s, auto_scan_interval_min: e.target.value })}
                className="bg-black/30 border-white/10 mono mt-1" />
            </div>
            <div>
              <label className="text-xs text-slate-400">Số trang kiểm tra (10 truyện/trang)</label>
              <Input data-testid="auto-scan-pages-input" type="number" min={1} value={s.auto_scan_pages}
                onChange={(e) => setS({ ...s, auto_scan_pages: e.target.value })}
                className="bg-black/30 border-white/10 mono mt-1" />
            </div>
            <div>
              <label className="text-xs text-slate-400">Số chương crawl / truyện (0 = tất cả)</label>
              <Input data-testid="chapter-limit-input" type="number" min={0} value={s.chapter_limit}
                onChange={(e) => setS({ ...s, chapter_limit: e.target.value })}
                className="bg-black/30 border-white/10 mono mt-1" />
            </div>
          </div>
        </div>

        <Button data-testid="save-settings-btn" onClick={save} className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-semibold">
          <Save className="h-4 w-4 mr-1.5" /> Lưu cấu hình
        </Button>
      </div>
    </div>
  );
}
