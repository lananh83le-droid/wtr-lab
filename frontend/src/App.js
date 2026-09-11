import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import { Toaster } from "sonner";
import { api } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import Dashboard from "@/components/Dashboard";
import NovelsTable from "@/components/NovelsTable";
import ProxyManager from "@/components/ProxyManager";
import LogsPanel from "@/components/LogsPanel";
import SettingsPanel from "@/components/SettingsPanel";

function App() {
  const [tab, setTab] = useState("dashboard");
  const [status, setStatus] = useState({ running: false, active: 0, throughput: 0, enumerate: {} });
  const [stats, setStats] = useState({});

  const refresh = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([api.crawlStatus(), api.stats()]);
      setStatus(s);
      setStats(st);
    } catch (e) {}
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="ops-bg min-h-screen text-foreground flex" data-testid="app-root">
      <Sidebar tab={tab} setTab={setTab} stats={stats} status={status} />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar status={status} stats={stats} onChange={refresh} />
        <main className="flex-1 p-6 max-w-[1700px] w-full mx-auto">
          {tab === "dashboard" && <Dashboard stats={stats} status={status} onChange={refresh} setTab={setTab} />}
          {tab === "novels" && <NovelsTable status={status} onChange={refresh} />}
          {tab === "proxies" && <ProxyManager />}
          {tab === "logs" && <LogsPanel />}
          {tab === "settings" && <SettingsPanel />}
        </main>
      </div>
      <Toaster theme="dark" position="top-right" richColors />
    </div>
  );
}

export default App;
