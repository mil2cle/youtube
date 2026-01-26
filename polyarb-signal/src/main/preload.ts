// =====================================================
// PolyArb Signal - Preload Script
// Secure bridge between main and renderer processes
// =====================================================

import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../shared/types';

// Expose protected methods to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  // Settings
  getSettings: () => ipcRenderer.invoke(IPC_CHANNELS.GET_SETTINGS),
  saveSettings: (settings: any) => ipcRenderer.invoke(IPC_CHANNELS.SAVE_SETTINGS, settings),

  // Telegram
  testTelegram: (credentials?: { botToken: string; chatId: string }) => 
    ipcRenderer.invoke(IPC_CHANNELS.TEST_TELEGRAM, credentials),

  // Scanning
  startScanning: () => ipcRenderer.invoke(IPC_CHANNELS.START_SCANNING),
  stopScanning: () => ipcRenderer.invoke(IPC_CHANNELS.STOP_SCANNING),

  // Stats
  getStats: () => ipcRenderer.invoke(IPC_CHANNELS.GET_STATS),

  // Logs
  getLogs: (limit?: number) => ipcRenderer.invoke(IPC_CHANNELS.GET_LOGS, limit),
  exportLogs: () => ipcRenderer.invoke(IPC_CHANNELS.EXPORT_LOGS),

  // Markets
  getMarkets: () => ipcRenderer.invoke(IPC_CHANNELS.GET_MARKETS),
  pinMarket: (marketId: string) => ipcRenderer.invoke(IPC_CHANNELS.PIN_MARKET, marketId),
  unpinMarket: (marketId: string) => ipcRenderer.invoke(IPC_CHANNELS.UNPIN_MARKET, marketId),
  blacklistMarket: (marketId: string) => ipcRenderer.invoke(IPC_CHANNELS.BLACKLIST_MARKET, marketId),

  // Event listeners
  onSignalDetected: (callback: (signal: any) => void) => {
    ipcRenderer.on(IPC_CHANNELS.SIGNAL_DETECTED, (_, signal) => callback(signal));
  },
  onStatsUpdate: (callback: (stats: any) => void) => {
    ipcRenderer.on(IPC_CHANNELS.STATS_UPDATE, (_, stats) => callback(stats));
  },
  onLogUpdate: (callback: (log: any) => void) => {
    ipcRenderer.on(IPC_CHANNELS.LOG_UPDATE, (_, log) => callback(log));
  },
  onStatusChange: (callback: (status: any) => void) => {
    ipcRenderer.on(IPC_CHANNELS.STATUS_CHANGE, (_, status) => callback(status));
  },

  // Remove listeners
  removeAllListeners: (channel: string) => {
    ipcRenderer.removeAllListeners(channel);
  },
});

// Type definitions for renderer
declare global {
  interface Window {
    electronAPI: {
      getSettings: () => Promise<any>;
      saveSettings: (settings: any) => Promise<{ success: boolean }>;
      testTelegram: (credentials?: { botToken: string; chatId: string }) => Promise<{ success: boolean; error?: string }>;
      startScanning: () => Promise<{ success: boolean }>;
      stopScanning: () => Promise<{ success: boolean }>;
      getStats: () => Promise<any>;
      getLogs: (limit?: number) => Promise<any[]>;
      exportLogs: () => Promise<{ logs: any[]; exportedAt: string }>;
      getMarkets: () => Promise<any[]>;
      pinMarket: (marketId: string) => Promise<{ success: boolean }>;
      unpinMarket: (marketId: string) => Promise<{ success: boolean }>;
      blacklistMarket: (marketId: string) => Promise<{ success: boolean }>;
      onSignalDetected: (callback: (signal: any) => void) => void;
      onStatsUpdate: (callback: (stats: any) => void) => void;
      onLogUpdate: (callback: (log: any) => void) => void;
      onStatusChange: (callback: (status: any) => void) => void;
      removeAllListeners: (channel: string) => void;
    };
  }
}
