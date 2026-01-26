// =====================================================
// PolyArb Signal - Main App Component
// =====================================================

import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Logs from './pages/Logs';
import Markets from './pages/Markets';

// Define types locally to avoid import issues in production
interface DashboardStats {
  totalMarkets: number;
  tierAMarkets: number;
  tierBMarkets: number;
  signalsToday: number;
  lastScanTime: number;
  status: 'running' | 'paused' | 'error';
  wsConnected: boolean;
}

interface SignalLogEntry {
  id: string;
  timestamp: number;
  marketQuestion: string;
  yesAsk: number;
  noAsk: number;
  gap: number;
  polymarketUrl: string;
  sent: boolean;
  tier: 'A' | 'B';
}

interface ArbSignal {
  id: string;
  timestamp: number;
  marketId: string;
  marketQuestion: string;
  yesAsk: number;
  noAsk: number;
  rawGap: number;
  effectiveEdge: number;
  yesDepth: number;
  noDepth: number;
  isLowDepth: boolean;
  polymarketUrl: string;
  tier: 'A' | 'B';
}

type TabType = 'dashboard' | 'markets' | 'logs' | 'settings';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [logs, setLogs] = useState<SignalLogEntry[]>([]);
  const [latestSignal, setLatestSignal] = useState<ArbSignal | null>(null);
  const [isElectronReady, setIsElectronReady] = useState(false);

  useEffect(() => {
    // Check if electronAPI is available
    if (typeof window !== 'undefined' && window.electronAPI) {
      setIsElectronReady(true);
      loadInitialData();

      // Setup event listeners
      window.electronAPI.onStatsUpdate((newStats: DashboardStats) => {
        setStats(newStats);
      });

      window.electronAPI.onLogUpdate((log: SignalLogEntry) => {
        setLogs(prev => [log, ...prev].slice(0, 100));
      });

      window.electronAPI.onSignalDetected((signal: ArbSignal) => {
        setLatestSignal(signal);
        // Clear after 10 seconds
        setTimeout(() => setLatestSignal(null), 10000);
      });
    } else {
      console.log('electronAPI not available yet, waiting...');
      // Retry after a short delay
      const timer = setTimeout(() => {
        if (window.electronAPI) {
          setIsElectronReady(true);
          loadInitialData();
        }
      }, 1000);
      return () => clearTimeout(timer);
    }

    return () => {
      // Cleanup listeners
    };
  }, []);

  const loadInitialData = async () => {
    if (!window.electronAPI) return;
    
    try {
      const [statsData, logsData] = await Promise.all([
        window.electronAPI.getStats(),
        window.electronAPI.getLogs(100),
      ]);
      setStats(statsData);
      setLogs(logsData);
    } catch (error) {
      console.error('Error loading initial data:', error);
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard stats={stats} latestSignal={latestSignal} />;
      case 'markets':
        return <Markets />;
      case 'logs':
        return <Logs logs={logs} />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard stats={stats} latestSignal={latestSignal} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-white">P</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">PolyArb Signal</h1>
              <p className="text-xs text-slate-400">Polymarket Arbitrage Detection</p>
            </div>
          </div>
          
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${stats?.status === 'running' ? 'bg-green-500' : 'bg-yellow-500'}`} />
            <span className="text-sm text-slate-300">
              {stats?.status === 'running' ? 'กำลังสแกน' : 'หยุดอยู่'}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex gap-1 mt-4">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'dashboard' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            แดชบอร์ด
          </button>
          <button
            onClick={() => setActiveTab('markets')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'markets' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            ตลาด
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'logs' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            บันทึก
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'settings' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            ตั้งค่า
          </button>
        </nav>
      </header>

      {/* Main content */}
      <main className="p-6">
        {renderContent()}
      </main>

      {/* Signal notification toast */}
      {latestSignal && (
        <div className="fixed bottom-4 right-4 bg-green-600 text-white px-4 py-3 rounded-lg shadow-lg">
          <div className="flex items-center gap-2">
            <span className="text-lg">🎯</span>
            <div>
              <p className="font-medium">Signal Detected!</p>
              <p className="text-sm opacity-90">
                Edge: {(latestSignal.effectiveEdge * 100).toFixed(2)}%
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
