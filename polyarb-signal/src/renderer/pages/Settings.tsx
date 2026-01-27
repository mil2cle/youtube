// =====================================================
// PolyArb Signal - Settings Page
// =====================================================

import React, { useState, useEffect } from 'react';

// Define types and defaults locally
interface AppSettings {
  telegram: {
    botToken: string;
    chatId: string;
  };
  scanning: {
    threshold: number;
    feeBuffer: number;
    cooldownMs: number;
    debounceMs: number;
  };
  filters: {
    minLiquidityUsd: number;
    minVolume24hUsd: number;
    minTopAskSizeUsd: number;
    maxSpread: number;
  };
  tiering: {
    tierAMax: number;
    tierAIntervalMs: number;
    tierBIntervalMs: number;
    burstMinutes: number;
  };
  general: {
    startOnBoot: boolean;
    minimizeToTray: boolean;
    sendLowDepthAlerts: boolean;
  };
}

interface WSStatusInfo {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'degraded' | 'error';
  message: string;
  messagesReceived: number;
  lastMessageTime: number | null;
  reconnectAttempts: number;
  subscribedAssets: number;
}

const DEFAULT_SETTINGS: AppSettings = {
  telegram: {
    botToken: '',
    chatId: '',
  },
  scanning: {
    threshold: 0.01,
    feeBuffer: 0.004,
    cooldownMs: 180000,
    debounceMs: 500,
  },
  filters: {
    minLiquidityUsd: 5000,
    minVolume24hUsd: 1000,
    minTopAskSizeUsd: 50,
    maxSpread: 0.10,
  },
  tiering: {
    tierAMax: 50,
    tierAIntervalMs: 3000,
    tierBIntervalMs: 30000,
    burstMinutes: 5,
  },
  general: {
    startOnBoot: false,
    minimizeToTray: true,
    sendLowDepthAlerts: false,
  },
};

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isTestingWs, setIsTestingWs] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; error?: string } | null>(null);
  const [wsTestResult, setWsTestResult] = useState<{ success: boolean; message: string; messagesReceived: number; latencyMs: number } | null>(null);
  const [wsStatus, setWsStatus] = useState<WSStatusInfo | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [testTokenIds, setTestTokenIds] = useState<string>('');

  useEffect(() => {
    loadSettings();
    loadWsStatus();
    
    // Poll WS status every 5 seconds
    const interval = setInterval(loadWsStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadSettings = async () => {
    if (!window.electronAPI) return;
    try {
      const loadedSettings = await window.electronAPI.getSettings();
      setSettings(loadedSettings);
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };

  const loadWsStatus = async () => {
    if (!window.electronAPI?.getWsStatus) return;
    try {
      const status = await window.electronAPI.getWsStatus();
      setWsStatus(status);
    } catch (error) {
      console.error('Error loading WS status:', error);
    }
  };

  const handleSave = async () => {
    if (!window.electronAPI) return;
    setIsSaving(true);
    setSaveMessage(null);
    try {
      await window.electronAPI.saveSettings(settings);
      setSaveMessage('บันทึกสำเร็จ!');
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error) {
      console.error('Error saving settings:', error);
      setSaveMessage('เกิดข้อผิดพลาดในการบันทึก');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!window.electronAPI) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await window.electronAPI.testTelegram({
        botToken: settings.telegram.botToken,
        chatId: settings.telegram.chatId,
      });
      setTestResult(result);
    } catch (error) {
      setTestResult({ success: false, error: 'เกิดข้อผิดพลาด' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleTestWebSocket = async () => {
    if (!window.electronAPI?.testWebSocket) return;
    setIsTestingWs(true);
    setWsTestResult(null);
    try {
      // Parse token IDs from input or use default test tokens
      let tokenIds: string[] = [];
      if (testTokenIds.trim()) {
        tokenIds = testTokenIds.split(',').map(id => id.trim()).filter(id => id.length > 0);
      }
      
      // If no custom tokens, get some from markets
      if (tokenIds.length === 0) {
        const markets = await window.electronAPI.getMarkets();
        if (markets && markets.length > 0) {
          // Get first 2 markets' token IDs
          tokenIds = markets.slice(0, 2).flatMap((m: any) => [m.yesTokenId, m.noTokenId]);
        }
      }

      if (tokenIds.length === 0) {
        setWsTestResult({
          success: false,
          message: 'ไม่มี token ID สำหรับทดสอบ กรุณาเริ่มสแกนก่อน',
          messagesReceived: 0,
          latencyMs: 0,
        });
        return;
      }

      const result = await window.electronAPI.testWebSocket(tokenIds);
      setWsTestResult(result);
    } catch (error) {
      setWsTestResult({
        success: false,
        message: `เกิดข้อผิดพลาด: ${error}`,
        messagesReceived: 0,
        latencyMs: 0,
      });
    } finally {
      setIsTestingWs(false);
    }
  };

  const updateSetting = <K extends keyof AppSettings>(
    category: K,
    key: keyof AppSettings[K],
    value: any
  ) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value,
      },
    }));
  };

  const getWsStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-400';
      case 'connecting':
      case 'reconnecting': return 'text-yellow-400';
      case 'degraded': return 'text-orange-400';
      case 'error': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  const getWsStatusText = (status: string) => {
    switch (status) {
      case 'connected': return '🟢 เชื่อมต่อแล้ว';
      case 'connecting': return '🟡 กำลังเชื่อมต่อ...';
      case 'reconnecting': return '🟡 กำลังเชื่อมต่อใหม่...';
      case 'degraded': return '🟠 Degraded (ใช้ REST)';
      case 'error': return '🔴 Error';
      default: return '⚪ ไม่ได้เชื่อมต่อ';
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Telegram Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>📱</span>
          Telegram
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Bot Token</label>
            <input
              type="password"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              value={settings.telegram.botToken}
              onChange={(e) => updateSetting('telegram', 'botToken', e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-1">
              สร้าง bot ผ่าน @BotFather บน Telegram
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Chat ID</label>
            <input
              type="text"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
              placeholder="-1001234567890"
              value={settings.telegram.chatId}
              onChange={(e) => updateSetting('telegram', 'chatId', e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-1">
              ใช้ @userinfobot เพื่อดู Chat ID ของคุณ
            </p>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={handleTestTelegram}
              disabled={isTesting || !settings.telegram.botToken || !settings.telegram.chatId}
              className="px-4 py-2 bg-slate-600 hover:bg-slate-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {isTesting ? 'กำลังทดสอบ...' : 'ทดสอบการเชื่อมต่อ'}
            </button>
            {testResult && (
              <span className={testResult.success ? 'text-green-400' : 'text-red-400'}>
                {testResult.success ? '✓ สำเร็จ' : `✗ ${testResult.error}`}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* WebSocket Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>🔌</span>
          WebSocket (Real-time Updates)
        </h3>
        
        <div className="space-y-4">
          {/* Status Display */}
          <div className="bg-slate-700/50 rounded-lg p-3">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-slate-400">สถานะ:</span>
                <span className={`ml-2 ${wsStatus ? getWsStatusColor(wsStatus.status) : 'text-slate-400'}`}>
                  {wsStatus ? getWsStatusText(wsStatus.status) : '⚪ ไม่ทราบ'}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Messages รับ:</span>
                <span className="ml-2 text-white">{wsStatus?.messagesReceived || 0}</span>
              </div>
              <div>
                <span className="text-slate-400">Subscribed:</span>
                <span className="ml-2 text-white">{wsStatus?.subscribedAssets || 0} tokens</span>
              </div>
              <div>
                <span className="text-slate-400">รายละเอียด:</span>
                <span className="ml-2 text-slate-300 text-xs">{wsStatus?.message || '-'}</span>
              </div>
            </div>
          </div>

          {/* Test Token IDs Input */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Token IDs สำหรับทดสอบ (ไม่บังคับ)
            </label>
            <input
              type="text"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 text-sm"
              placeholder="เว้นว่างเพื่อใช้ token จากตลาดที่กำลังสแกน"
              value={testTokenIds}
              onChange={(e) => setTestTokenIds(e.target.value)}
            />
            <p className="text-xs text-slate-500 mt-1">
              คั่นด้วย comma ถ้าต้องการทดสอบหลาย token
            </p>
          </div>

          {/* Test Button */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleTestWebSocket}
              disabled={isTestingWs}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {isTestingWs ? 'กำลังทดสอบ (10 วินาที)...' : '🧪 Test WebSocket'}
            </button>
            {wsTestResult && (
              <span className={wsTestResult.success ? 'text-green-400' : 'text-yellow-400'}>
                {wsTestResult.success 
                  ? `✓ ${wsTestResult.message}` 
                  : `⚠ ${wsTestResult.message}`}
              </span>
            )}
          </div>

          {/* Info Box */}
          <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-3 text-sm">
            <p className="text-blue-300">
              <strong>💡 หมายเหตุ:</strong> WebSocket ใช้สำหรับรับ real-time orderbook updates
              จาก Polymarket ถ้าเชื่อมต่อไม่ได้ แอปจะใช้ REST polling แทน (Degraded mode)
            </p>
          </div>
        </div>
      </div>

      {/* Scanning Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>🔍</span>
          การสแกน
        </h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Threshold (%)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              step="0.1"
              min="0"
              max="10"
              value={settings.scanning.threshold * 100}
              onChange={(e) => updateSetting('scanning', 'threshold', parseFloat(e.target.value) / 100)}
            />
            <p className="text-xs text-slate-500 mt-1">
              ส่ง signal เมื่อ edge ≥ ค่านี้
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Fee Buffer (%)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              step="0.1"
              min="0"
              max="5"
              value={settings.scanning.feeBuffer * 100}
              onChange={(e) => updateSetting('scanning', 'feeBuffer', parseFloat(e.target.value) / 100)}
            />
            <p className="text-xs text-slate-500 mt-1">
              หักค่าธรรมเนียมโดยประมาณ
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Cooldown (วินาที)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="0"
              value={settings.scanning.cooldownMs / 1000}
              onChange={(e) => updateSetting('scanning', 'cooldownMs', parseInt(e.target.value) * 1000)}
            />
            <p className="text-xs text-slate-500 mt-1">
              รอก่อนส่ง signal ซ้ำ
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Debounce (ms)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="0"
              value={settings.scanning.debounceMs}
              onChange={(e) => updateSetting('scanning', 'debounceMs', parseInt(e.target.value))}
            />
            <p className="text-xs text-slate-500 mt-1">
              รอยืนยันก่อนส่ง signal
            </p>
          </div>
        </div>
      </div>

      {/* Filter Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>🎯</span>
          ตัวกรอง
        </h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Liquidity ขั้นต่ำ ($)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="0"
              value={settings.filters.minLiquidityUsd}
              onChange={(e) => updateSetting('filters', 'minLiquidityUsd', parseInt(e.target.value))}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Volume 24h ขั้นต่ำ ($)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="0"
              value={settings.filters.minVolume24hUsd}
              onChange={(e) => updateSetting('filters', 'minVolume24hUsd', parseInt(e.target.value))}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Top Ask Size ขั้นต่ำ ($)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="0"
              value={settings.filters.minTopAskSizeUsd}
              onChange={(e) => updateSetting('filters', 'minTopAskSizeUsd', parseInt(e.target.value))}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Spread สูงสุด (%)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              step="0.1"
              min="0"
              max="20"
              value={settings.filters.maxSpread * 100}
              onChange={(e) => updateSetting('filters', 'maxSpread', parseFloat(e.target.value) / 100)}
            />
          </div>
        </div>
      </div>

      {/* Tiering Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>📊</span>
          Tiering
        </h3>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Tier A สูงสุด (ตลาด)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="1"
              max="200"
              value={settings.tiering.tierAMax}
              onChange={(e) => updateSetting('tiering', 'tierAMax', parseInt(e.target.value))}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Tier A Interval (วินาที)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="1"
              value={settings.tiering.tierAIntervalMs / 1000}
              onChange={(e) => updateSetting('tiering', 'tierAIntervalMs', parseInt(e.target.value) * 1000)}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Tier B Interval (วินาที)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="1"
              value={settings.tiering.tierBIntervalMs / 1000}
              onChange={(e) => updateSetting('tiering', 'tierBIntervalMs', parseInt(e.target.value) * 1000)}
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Burst Mode (นาที)
            </label>
            <input
              type="number"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              min="1"
              value={settings.tiering.burstMinutes}
              onChange={(e) => updateSetting('tiering', 'burstMinutes', parseInt(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* General Settings */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>⚙️</span>
          ทั่วไป
        </h3>
        
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer text-white">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
              checked={settings.general.startOnBoot}
              onChange={(e) => updateSetting('general', 'startOnBoot', e.target.checked)}
            />
            <span>เริ่มสแกนอัตโนมัติเมื่อเปิดโปรแกรม</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-white">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
              checked={settings.general.minimizeToTray}
              onChange={(e) => updateSetting('general', 'minimizeToTray', e.target.checked)}
            />
            <span>ย่อไปที่ System Tray เมื่อปิดหน้าต่าง</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer text-white">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border border-slate-600 text-blue-600 focus:ring-blue-500"
              checked={settings.general.sendLowDepthAlerts}
              onChange={(e) => updateSetting('general', 'sendLowDepthAlerts', e.target.checked)}
            />
            <span>ส่งแจ้งเตือนแม้ depth ต่ำ</span>
          </label>
        </div>
      </div>

      {/* Save button */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
        >
          {isSaving ? 'กำลังบันทึก...' : 'บันทึกการตั้งค่า'}
        </button>
        {saveMessage && (
          <span className={saveMessage.includes('สำเร็จ') ? 'text-green-400' : 'text-red-400'}>
            {saveMessage}
          </span>
        )}
      </div>
    </div>
  );
};

export default Settings;
