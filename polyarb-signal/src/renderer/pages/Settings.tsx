// =====================================================
// PolyArb Signal - Settings Page
// =====================================================

import React, { useState, useEffect } from 'react';
import { AppSettings } from '@shared/types';
import { DEFAULT_SETTINGS } from '@shared/constants';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS as AppSettings);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; error?: string } | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const loadedSettings = await window.electronAPI.getSettings();
      setSettings(loadedSettings);
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };

  const handleSave = async () => {
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
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await window.electronAPI.testTelegram();
      setTestResult(result);
    } catch (error) {
      setTestResult({ success: false, error: 'เกิดข้อผิดพลาด' });
    } finally {
      setIsTesting(false);
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

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Telegram Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>📱</span>
          Telegram
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Bot Token</label>
            <input
              type="password"
              className="input"
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
              className="input"
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
              className="btn btn-secondary"
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

      {/* Scanning Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
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
              className="input"
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
              className="input"
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
              className="input"
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
              className="input"
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
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
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
              className="input"
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
              className="input"
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
              className="input"
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
              className="input"
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
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
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
              className="input"
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
              className="input"
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
              className="input"
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
              className="input"
              min="1"
              value={settings.tiering.burstMinutes}
              onChange={(e) => updateSetting('tiering', 'burstMinutes', parseInt(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* General Settings */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span>⚙️</span>
          ทั่วไป
        </h3>
        
        <div className="space-y-3">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
              checked={settings.general.startOnBoot}
              onChange={(e) => updateSetting('general', 'startOnBoot', e.target.checked)}
            />
            <span>เริ่มสแกนอัตโนมัติเมื่อเปิดโปรแกรม</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
              checked={settings.general.minimizeToTray}
              onChange={(e) => updateSetting('general', 'minimizeToTray', e.target.checked)}
            />
            <span>ย่อไปที่ System Tray เมื่อปิดหน้าต่าง</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              className="w-5 h-5 rounded bg-slate-700 border-slate-600 text-blue-600 focus:ring-blue-500"
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
          className="btn btn-primary"
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
