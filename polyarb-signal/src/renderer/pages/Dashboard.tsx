// =====================================================
// PolyArb Signal - Dashboard Page
// =====================================================

import React, { useState } from 'react';

// Define types locally
interface DashboardStats {
  totalMarkets: number;
  tierAMarkets: number;
  tierBMarkets: number;
  signalsToday: number;
  lastScanTime: number;
  status: 'running' | 'paused' | 'error';
  wsConnected: boolean;
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
  yesAskDepth?: number;
  noAskDepth?: number;
  isLowDepth: boolean;
  polymarketUrl: string;
  tier: 'A' | 'B';
}

interface DashboardProps {
  stats: DashboardStats | null;
  latestSignal: ArbSignal | null;
}

const Dashboard: React.FC<DashboardProps> = ({ stats, latestSignal }) => {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const handleStart = async () => {
    if (!window.electronAPI) return;
    setIsStarting(true);
    try {
      await window.electronAPI.startScanning();
    } catch (error) {
      console.error('Error starting:', error);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    if (!window.electronAPI) return;
    setIsStopping(true);
    try {
      await window.electronAPI.stopScanning();
    } catch (error) {
      console.error('Error stopping:', error);
    } finally {
      setIsStopping(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Control buttons */}
      <div className="flex gap-4">
        <button
          onClick={handleStart}
          disabled={isStarting || stats?.status === 'running'}
          className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          {isStarting ? (
            <>
              <span className="animate-spin">⏳</span>
              กำลังเริ่ม...
            </>
          ) : (
            <>
              <span>▶️</span>
              เริ่มสแกน
            </>
          )}
        </button>
        <button
          onClick={handleStop}
          disabled={isStopping || stats?.status !== 'running'}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          {isStopping ? (
            <>
              <span className="animate-spin">⏳</span>
              กำลังหยุด...
            </>
          ) : (
            <>
              <span>⏹️</span>
              หยุดสแกน
            </>
          )}
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="ตลาดทั้งหมด"
          value={stats?.totalMarkets ?? 0}
          icon="📊"
          color="blue"
        />
        <StatCard
          title="Tier A"
          value={stats?.tierAMarkets ?? 0}
          icon="⚡"
          color="green"
          subtitle="สแกนทุก 3 วินาที"
        />
        <StatCard
          title="Tier B"
          value={stats?.tierBMarkets ?? 0}
          icon="🔄"
          color="yellow"
          subtitle="สแกนทุก 30 วินาที"
        />
        <StatCard
          title="Signals วันนี้"
          value={stats?.signalsToday ?? 0}
          icon="🎯"
          color="purple"
        />
      </div>

      {/* Connection status */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">สถานะการเชื่อมต่อ</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${stats?.status === 'running' ? 'bg-green-500' : 'bg-yellow-500'}`} />
            <div>
              <p className="text-sm text-slate-400">Signal Engine</p>
              <p className="font-medium text-white">{stats?.status === 'running' ? 'กำลังทำงาน' : 'หยุดอยู่'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${stats?.wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <div>
              <p className="text-sm text-slate-400">WebSocket</p>
              <p className="font-medium text-white">{stats?.wsConnected ? 'เชื่อมต่อแล้ว' : 'ไม่ได้เชื่อมต่อ'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Latest signal */}
      {latestSignal && (
        <div className="bg-slate-800 rounded-lg p-4 border border-green-500/50">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-green-400 flex items-center gap-2">
                <span>🎯</span>
                Signal ล่าสุด
              </h3>
              <p className="text-slate-300 mt-2">{latestSignal.marketQuestion}</p>
            </div>
            <span className={`px-2 py-1 rounded text-xs font-bold ${
              latestSignal.tier === 'A' ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'
            }`}>
              Tier {latestSignal.tier}
            </span>
          </div>
          
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div>
              <p className="text-sm text-slate-400">YES Ask</p>
              <p className="text-xl font-bold text-green-400">
                {(latestSignal.yesAsk * 100).toFixed(1)}¢
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-400">NO Ask</p>
              <p className="text-xl font-bold text-red-400">
                {(latestSignal.noAsk * 100).toFixed(1)}¢
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Edge</p>
              <p className="text-xl font-bold text-blue-400">
                {(latestSignal.effectiveEdge * 100).toFixed(2)}%
              </p>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <div className="text-sm text-slate-400">
              Depth: YES ${(latestSignal.yesAskDepth || latestSignal.yesDepth || 0).toFixed(0)} / NO ${(latestSignal.noAskDepth || latestSignal.noDepth || 0).toFixed(0)}
            </div>
            <a
              href={latestSignal.polymarketUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm transition-colors"
            >
              เปิดใน Polymarket →
            </a>
          </div>
        </div>
      )}

      {/* Info box */}
      <div className="bg-blue-900/30 rounded-lg p-4 border border-blue-700">
        <h3 className="font-semibold text-blue-300 mb-2">💡 วิธีใช้งาน</h3>
        <ul className="text-sm text-slate-300 space-y-1">
          <li>• กด "เริ่มสแกน" เพื่อเริ่มตรวจจับโอกาส arbitrage</li>
          <li>• ตั้งค่า Telegram Bot Token และ Chat ID ในหน้าตั้งค่าเพื่อรับแจ้งเตือน</li>
          <li>• ตลาดที่มีโอกาส arb สูงจะถูกย้ายไป Tier A โดยอัตโนมัติ</li>
          <li>• Signal จะถูกส่งเมื่อ effective edge ≥ threshold ที่ตั้งไว้</li>
        </ul>
      </div>
    </div>
  );
};

// Stat card component
interface StatCardProps {
  title: string;
  value: number;
  icon: string;
  color: 'blue' | 'green' | 'yellow' | 'purple';
  subtitle?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color, subtitle }) => {
  const colorClasses = {
    blue: 'bg-blue-600/20 border-blue-600/50',
    green: 'bg-green-600/20 border-green-600/50',
    yellow: 'bg-yellow-600/20 border-yellow-600/50',
    purple: 'bg-purple-600/20 border-purple-600/50',
  };

  const textClasses = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  };

  return (
    <div className={`rounded-lg p-4 border ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        <span className={`text-3xl font-bold ${textClasses[color]}`}>{value}</span>
      </div>
      <p className="mt-2 text-sm text-slate-300">{title}</p>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
    </div>
  );
};

export default Dashboard;
