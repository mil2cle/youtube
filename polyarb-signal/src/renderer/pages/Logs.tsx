// =====================================================
// PolyArb Signal - Logs Page
// =====================================================

import React, { useState } from 'react';
import { SignalLogEntry } from '@shared/types';

interface LogsProps {
  logs: SignalLogEntry[];
}

const Logs: React.FC<LogsProps> = ({ logs }) => {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
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
        <h2 className="text-xl font-semibold">บันทึก Signal ({logs.length})</h2>
        <button
          onClick={handleExport}
          disabled={isExporting || logs.length === 0}
          className="btn btn-secondary"
        >
          {isExporting ? 'กำลังส่งออก...' : '📥 ส่งออก JSON'}
        </button>
      </div>

      {/* Logs table */}
      {logs.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">ยังไม่มี signal</p>
          <p className="text-sm text-slate-500 mt-2">
            เริ่มสแกนเพื่อตรวจจับโอกาส arbitrage
          </p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>เวลา</th>
                  <th>ตลาด</th>
                  <th>YES</th>
                  <th>NO</th>
                  <th>Edge</th>
                  <th>Tier</th>
                  <th>ส่ง</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="text-sm text-slate-400 whitespace-nowrap">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="max-w-xs truncate" title={log.marketQuestion}>
                      {log.marketQuestion}
                    </td>
                    <td className="text-green-400 font-mono">
                      {(log.yesAsk * 100).toFixed(1)}¢
                    </td>
                    <td className="text-red-400 font-mono">
                      {(log.noAsk * 100).toFixed(1)}¢
                    </td>
                    <td className="text-blue-400 font-bold">
                      {(log.gap * 100).toFixed(2)}%
                    </td>
                    <td>
                      <span className={`tier-badge ${log.tier === 'A' ? 'tier-a' : 'tier-b'}`}>
                        {log.tier}
                      </span>
                    </td>
                    <td>
                      {log.sent ? (
                        <span className="text-green-400">✓</span>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </td>
                    <td>
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
          <div className="card text-center">
            <p className="text-2xl font-bold text-blue-400">
              {(logs.reduce((sum, l) => sum + l.gap, 0) / logs.length * 100).toFixed(2)}%
            </p>
            <p className="text-sm text-slate-400">Edge เฉลี่ย</p>
          </div>
          <div className="card text-center">
            <p className="text-2xl font-bold text-green-400">
              {logs.filter(l => l.sent).length}
            </p>
            <p className="text-sm text-slate-400">ส่ง Telegram</p>
          </div>
          <div className="card text-center">
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
