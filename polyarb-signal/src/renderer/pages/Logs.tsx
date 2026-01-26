// =====================================================
// PolyArb Signal - Logs Page
// =====================================================

import React, { useState } from 'react';

// Define types locally
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

interface LogsProps {
  logs: SignalLogEntry[];
}

const Logs: React.FC<LogsProps> = ({ logs }) => {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!window.electronAPI) return;
    setIsExporting(true);
    try {
      const data = await window.electronAPI.exportLogs();
      
      // Create and download JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `polyarb-signals-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting logs:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('th-TH', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">บันทึก Signal ({logs.length})</h2>
        <button
          onClick={handleExport}
          disabled={isExporting || logs.length === 0}
          className="px-4 py-2 bg-slate-600 hover:bg-slate-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >
          {isExporting ? 'กำลังส่งออก...' : '📥 ส่งออก JSON'}
        </button>
      </div>

      {/* Logs table */}
      {logs.length === 0 ? (
        <div className="bg-slate-800 rounded-lg p-12 text-center border border-slate-700">
          <p className="text-slate-400">ยังไม่มี signal</p>
          <p className="text-sm text-slate-500 mt-2">
            เริ่มสแกนเพื่อตรวจจับโอกาส arbitrage
          </p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-700">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">เวลา</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">ตลาด</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">YES</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">NO</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Edge</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Tier</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">ส่ง</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-slate-300"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-700/50">
                    <td className="px-4 py-3 text-sm text-slate-400 whitespace-nowrap">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-white max-w-xs truncate" title={log.marketQuestion}>
                      {log.marketQuestion}
                    </td>
                    <td className="px-4 py-3 text-green-400 font-mono">
                      {(log.yesAsk * 100).toFixed(1)}¢
                    </td>
                    <td className="px-4 py-3 text-red-400 font-mono">
                      {(log.noAsk * 100).toFixed(1)}¢
                    </td>
                    <td className="px-4 py-3 text-blue-400 font-bold">
                      {(log.gap * 100).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        log.tier === 'A' ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'
                      }`}>
                        {log.tier}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {log.sent ? (
                        <span className="text-green-400">✓</span>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <a
                        href={log.polymarketUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 text-sm"
                      >
                        เปิด →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stats summary */}
      {logs.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-slate-800 rounded-lg p-4 text-center border border-slate-700">
            <p className="text-2xl font-bold text-blue-400">
              {(logs.reduce((sum, l) => sum + l.gap, 0) / logs.length * 100).toFixed(2)}%
            </p>
            <p className="text-sm text-slate-400">Edge เฉลี่ย</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center border border-slate-700">
            <p className="text-2xl font-bold text-green-400">
              {logs.filter(l => l.sent).length}
            </p>
            <p className="text-sm text-slate-400">ส่ง Telegram</p>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center border border-slate-700">
            <p className="text-2xl font-bold text-purple-400">
              {logs.filter(l => l.tier === 'A').length}
            </p>
            <p className="text-sm text-slate-400">จาก Tier A</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Logs;
