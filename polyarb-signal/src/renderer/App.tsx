// =====================================================
// PolyArb Signal - Main App Component
// =====================================================

import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Logs from './pages/Logs';
import Markets from './pages/Markets';
import { DashboardStats, SignalLogEntry, ArbSignal } from '@shared/types';

type TabType = 'dashboard' | 'markets' | 'logs' | 'settings';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [logs, setLogs] = useState<SignalLogEntry[]>([]);
  const [latestSignal, setLatestSignal] = useState<ArbSignal | null>(null);

  useEffect(() => {
    // Load initial data
    loadInitialData();

    // Setup event listeners
    window.electronAPI.onStatsUpdate((newStats) => {
      setStats(newStats);
    });

    window.electronAPI.onLogUpdate((log) => {
      setLogs(prev => [log, ...prev].slice(0, 100));
    });

    window.electronAPI.onSignalDetected((signal) => {
      setLatestSignal(signal);
      // Clear after 10 seconds
      setTimeout(() => setLatestSignal(null), 10000);
    });

    return () => {
      // Cleanup listeners
    };
  }, []);

  const loadInitialData = async () => {
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
              <span className="text-xl font-bold">P</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">PolyArb Signal</h1>
              <p className="text-xs text-slate-400">Polymarket Arbitrage Detection</p>
            </div>
          </div>
          
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className={`status-dot ${stats?.status === 'running' ? 'status-running' : 'status-paused'}`} />
            <span className="text-sm text-slate-300">
              {stats?.status === 'running' ? 'กำลังสแกน' : 'หยุดอยู่'}
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex gap-1 mt-4">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          >
            แดชบอร์ด
          </button>
          <button
            onClick={() => setActiveTab('markets')}
            className={`nav-tab ${activeTab === 'markets' ? 'active' : ''}`}
          >
            ตลาด
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`nav-tab ${activeTab === 'logs' ? 'active' : ''}`}
          >
            บันทึก
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`nav-tab ${activeTab === 'settings' ? 'active' : ''}`}
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
        <div className="toast toast-success signal-card">
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
