// =====================================================
// PolyArb Signal - Settings Store
// Persistent settings storage using electron-store
// =====================================================

import Store from 'electron-store';
import { AppSettings, SignalLogEntry } from '../../shared/types';
import { DEFAULT_SETTINGS } from '../../shared/constants';
import { logger } from './logger';

interface StoreSchema {
  settings: AppSettings;
  signalLogs: SignalLogEntry[];
  pinnedMarkets: string[];
  blacklistedMarkets: string[];
}

class SettingsStore {
  private store: Store<StoreSchema>;

  constructor() {
    this.store = new Store<StoreSchema>({
      name: 'polyarb-signal-config',
      defaults: {
        settings: DEFAULT_SETTINGS as AppSettings,
        signalLogs: [],
        pinnedMarkets: [],
        blacklistedMarkets: [],
      },
    });

    logger.info('Settings store initialized');
  }

  // =====================================================
  // Settings
  // =====================================================

  getSettings(): AppSettings {
    return this.store.store.settings;
  }

  saveSettings(settings: AppSettings): void {
    this.store.store = { ...this.store.store, settings };
    logger.info('Settings saved');
  }

  resetSettings(): void {
    this.store.store = { ...this.store.store, settings: DEFAULT_SETTINGS as AppSettings };
    logger.info('Settings reset to defaults');
  }

  // =====================================================
  // Signal Logs
  // =====================================================

  getSignalLogs(limit: number = 100): SignalLogEntry[] {
    const logs = this.store.store.signalLogs || [];
    return logs.slice(-limit);
  }

  addSignalLog(entry: SignalLogEntry): void {
    const logs = [...(this.store.store.signalLogs || [])];
    logs.push(entry);
    
    // Keep only last 1000 entries
    if (logs.length > 1000) {
      logs.splice(0, logs.length - 1000);
    }
    
    this.store.store = { ...this.store.store, signalLogs: logs };
  }

  clearSignalLogs(): void {
    this.store.store = { ...this.store.store, signalLogs: [] };
    logger.info('Signal logs cleared');
  }

  // =====================================================
  // Pinned Markets
  // =====================================================

  getPinnedMarkets(): string[] {
    return this.store.store.pinnedMarkets || [];
  }

  addPinnedMarket(marketId: string): void {
    const pinned = [...(this.store.store.pinnedMarkets || [])];
    if (!pinned.includes(marketId)) {
      pinned.push(marketId);
      this.store.store = { ...this.store.store, pinnedMarkets: pinned };
    }
  }

  removePinnedMarket(marketId: string): void {
    const pinned = [...(this.store.store.pinnedMarkets || [])];
    const index = pinned.indexOf(marketId);
    if (index > -1) {
      pinned.splice(index, 1);
      this.store.store = { ...this.store.store, pinnedMarkets: pinned };
    }
  }

  // =====================================================
  // Blacklisted Markets
  // =====================================================

  getBlacklistedMarkets(): string[] {
    return this.store.store.blacklistedMarkets || [];
  }

  addBlacklistedMarket(marketId: string): void {
    const blacklisted = [...(this.store.store.blacklistedMarkets || [])];
    if (!blacklisted.includes(marketId)) {
      blacklisted.push(marketId);
      this.store.store = { ...this.store.store, blacklistedMarkets: blacklisted };
    }
    
    // Remove from pinned if present
    this.removePinnedMarket(marketId);
  }

  removeBlacklistedMarket(marketId: string): void {
    const blacklisted = [...(this.store.store.blacklistedMarkets || [])];
    const index = blacklisted.indexOf(marketId);
    if (index > -1) {
      blacklisted.splice(index, 1);
      this.store.store = { ...this.store.store, blacklistedMarkets: blacklisted };
    }
  }

  // =====================================================
  // Export
  // =====================================================

  exportLogs(): { logs: SignalLogEntry[]; exportedAt: string } {
    return {
      logs: this.store.store.signalLogs || [],
      exportedAt: new Date().toISOString(),
    };
  }
}

export const settingsStore = new SettingsStore();
export default settingsStore;
