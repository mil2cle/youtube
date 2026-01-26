// =====================================================
// PolyArb Signal - Dashboard Page
// =====================================================

import React, { useState } from 'react';
import { DashboardStats, ArbSignal } from '@shared/types';

interface DashboardProps {
  stats: DashboardStats | null;
  latestSignal: ArbSignal | null;
}

const Dashboard: React.FC<DashboardProps> = ({ stats, latestSignal }) => {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const handleStart = async () => {
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
          className="btn btn-success flex items-center gap-2"
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
          className="btn btn-danger flex items-center gap-2"
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
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">สถานะการเชื่อมต่อ</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <div className={`status-dot ${stats?.status === 'running' ? 'status-running' : 'status-paused'}`} />
            <div>
              <p className="text-sm text-slate-400">Signal Engine</p>
              <p className="font-medium">{stats?.status === 'running' ? 'กำลังทำงาน' : 'หยุดอยู่'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`status-dot ${stats?.wsConnected ? 'status-running' : 'status-error'}`} />
            <div>
              <p className="text-sm text-slate-400">WebSocket</p>
              <p className="font-medium">{stats?.wsConnected ? 'เชื่อมต่อแล้ว' : 'ไม่ได้เชื่อมต่อ'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Latest signal */}
      {latestSignal && (
        <div className="card border-green-500/50 signal-card">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-green-400 flex items-center gap-2">
                <span>🎯</span>
                Signal ล่าสุด
              </h3>
              <p className="text-slate-300 mt-2">{latestSignal.marketQuestion}</p>
            </div>
            <span className={`tier-badge ${latestSignal.tier === 'A' ? 'tier-a' : 'tier-b'}`}>
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
              Depth: YES ${latestSignal.yesAskDepth.toFixed(0)} / NO ${latestSignal.noAskDepth.toFixed(0)}
            </div>
            <a
              href={latestSignal.polymarketUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary text-sm"
            >
              เปิดใน Polymarket →
            </a>
          </div>
        </div>
      )}

      {/* Info box */}
      <div className="card bg-blue-900/30 border-blue-700">
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
    blue: 'bg-blue-600/20 border-blue-600/50 text-blue-400',
    green: 'bg-green-600/20 border-green-600/50 text-green-400',
    yellow: 'bg-yellow-600/20 border-yellow-600/50 text-yellow-400',
    purple: 'bg-purple-600/20 border-purple-600/50 text-purple-400',
  };

  return (
    <div className={`card ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        <span className="text-3xl font-bold">{value}</span>
      </div>
      <p className="mt-2 text-sm text-slate-300">{title}</p>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
    </div>
  );
};

export default Dashboard;
