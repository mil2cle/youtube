// =====================================================
// PolyArb Signal - Markets Page
// =====================================================

import React, { useState, useEffect } from 'react';
import { TieredMarket } from '@shared/types';

const Markets: React.FC = () => {
  const [markets, setMarkets] = useState<TieredMarket[]>([]);
  const [filter, setFilter] = useState<'all' | 'A' | 'B'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadMarkets();
    // Refresh every 30 seconds
    const interval = setInterval(loadMarkets, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadMarkets = async () => {
    try {
      const data = await window.electronAPI.getMarkets();
      setMarkets(data);
    } catch (error) {
      console.error('Error loading markets:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePin = async (marketId: string) => {
    try {
      await window.electronAPI.pinMarket(marketId);
      loadMarkets();
    } catch (error) {
      console.error('Error pinning market:', error);
    }
  };

  const handleUnpin = async (marketId: string) => {
    try {
      await window.electronAPI.unpinMarket(marketId);
      loadMarkets();
    } catch (error) {
      console.error('Error unpinning market:', error);
    }
  };

  const handleBlacklist = async (marketId: string) => {
    if (window.confirm('ต้องการ blacklist ตลาดนี้หรือไม่?')) {
      try {
        await window.electronAPI.blacklistMarket(marketId);
        loadMarkets();
      } catch (error) {
        console.error('Error blacklisting market:', error);
      }
    }
  };

  const filteredMarkets = markets
    .filter(m => filter === 'all' || m.tier === filter)
    .filter(m => 
      searchQuery === '' || 
      m.question.toLowerCase().includes(searchQuery.toLowerCase())
    );

  const tierACount = markets.filter(m => m.tier === 'A').length;
  const tierBCount = markets.filter(m => m.tier === 'B').length;

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`;
    return `$${num.toFixed(0)}`;
  };

  const formatTime = (timestamp: number) => {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">กำลังโหลด...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">ตลาด ({markets.length})</h2>
        <button
          onClick={loadMarkets}
          className="btn btn-secondary text-sm"
        >
          🔄 รีเฟรช
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('all')}
            className={`btn text-sm ${filter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
          >
            ทั้งหมด ({markets.length})
          </button>
          <button
            onClick={() => setFilter('A')}
            className={`btn text-sm ${filter === 'A' ? 'btn-primary' : 'btn-secondary'}`}
          >
            Tier A ({tierACount})
          </button>
          <button
            onClick={() => setFilter('B')}
            className={`btn text-sm ${filter === 'B' ? 'btn-primary' : 'btn-secondary'}`}
          >
            Tier B ({tierBCount})
          </button>
        </div>

        <input
          type="text"
          className="input max-w-xs"
          placeholder="ค้นหาตลาด..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Markets list */}
      {filteredMarkets.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">ไม่พบตลาด</p>
          <p className="text-sm text-slate-500 mt-2">
            {markets.length === 0 ? 'เริ่มสแกนเพื่อโหลดตลาด' : 'ลองเปลี่ยนตัวกรอง'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredMarkets.map((market) => (
            <div
              key={market.id}
              className={`card flex items-start justify-between gap-4 ${
                market.inBurstMode ? 'border-yellow-500/50' : ''
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`tier-badge ${market.tier === 'A' ? 'tier-a' : 'tier-b'}`}>
                    Tier {market.tier}
                  </span>
                  {market.inBurstMode && (
                    <span className="text-xs text-yellow-400">⚡ Burst Mode</span>
                  )}
                </div>
                <h3 className="font-medium text-slate-100 truncate" title={market.question}>
                  {market.question}
                </h3>
                <div className="flex items-center gap-4 mt-2 text-sm text-slate-400">
                  <span>💰 {formatNumber(market.liquidity)}</span>
                  <span>📊 {formatNumber(market.volume24h)}/24h</span>
                  <span>🕐 {formatTime(market.lastUpdate)}</span>
                  <span>🎯 {market.nearArbCount} signals</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {market.tier === 'A' ? (
                  <button
                    onClick={() => handleUnpin(market.id)}
                    className="btn btn-secondary text-sm"
                    title="Unpin"
                  >
                    📌
                  </button>
                ) : (
                  <button
                    onClick={() => handlePin(market.id)}
                    className="btn btn-secondary text-sm"
                    title="Pin to Tier A"
                  >
                    📍
                  </button>
                )}
                <button
                  onClick={() => handleBlacklist(market.id)}
                  className="btn btn-secondary text-sm text-red-400 hover:text-red-300"
                  title="Blacklist"
                >
                  🚫
                </button>
                <a
                  href={market.polymarketUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary text-sm"
                >
                  🔗
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="card bg-slate-800/50">
        <h4 className="font-medium mb-2">คำอธิบาย</h4>
        <div className="grid grid-cols-2 gap-2 text-sm text-slate-400">
          <div>📍 Pin - ย้ายไป Tier A ถาวร</div>
          <div>📌 Unpin - ปล่อยให้ระบบจัดการ</div>
          <div>🚫 Blacklist - ไม่สแกนตลาดนี้</div>
          <div>⚡ Burst Mode - สแกนถี่ชั่วคราว</div>
        </div>
      </div>
    </div>
  );
};

export default Markets;
