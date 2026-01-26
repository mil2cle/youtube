// =====================================================
// PolyArb Signal - Main Process Entry Point
// Electron desktop application
// =====================================================

import { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage } from 'electron';
import path from 'path';
import { logger } from './utils/logger';
import { settingsStore } from './utils/settingsStore';
import { gammaClient } from './services/gammaClient';
import { signalEngine } from './services/signalEngine';
import { telegramNotifier } from './services/telegramNotifier';
import { tieringSystem } from './services/tieringSystem';
import { wsClient } from './services/wsClient';
import { 
  ArbSignal, 
  AppSettings, 
  SignalLogEntry, 
  DashboardStats,
  IPC_CHANNELS 
} from '../shared/types';

// =====================================================
// Global State
// =====================================================

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;

// =====================================================
// Path Helpers
// =====================================================

function getPreloadPath(): string {
  return path.join(__dirname, 'preload.js');
}

function getRendererPath(): string {
  return path.join(__dirname, '../renderer/index.html');
}

// =====================================================
// Window Management
// =====================================================

function createWindow(): void {
  const settings = settingsStore.getSettings();

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'PolyArb Signal',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: getPreloadPath(),
    },
    show: false,
  });

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    const rendererPath = getRendererPath();
    logger.info(`Loading renderer from: ${rendererPath}`);
    mainWindow.loadFile(rendererPath);
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Handle close to tray
  mainWindow.on('close', (event) => {
    if (!isQuitting && settings.general.minimizeToTray) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Log any load errors
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    logger.error(`Failed to load: ${errorCode} - ${errorDescription}`);
  });

  logger.info('Main window created');
}

// =====================================================
// Tray Management
// =====================================================

function createTray(): void {
  try {
    // Create a simple tray icon
    const icon = nativeImage.createEmpty();
    tray = new Tray(icon);
    tray.setToolTip('PolyArb Signal');

    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'เปิดหน้าต่าง',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          } else {
            createWindow();
          }
        },
      },
      { type: 'separator' },
      {
        label: 'เริ่มสแกน',
        click: () => startScanning(),
      },
      {
        label: 'หยุดสแกน',
        click: () => stopScanning(),
      },
      { type: 'separator' },
      {
        label: 'ออกจากโปรแกรม',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(contextMenu);

    tray.on('double-click', () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      } else {
        createWindow();
      }
    });

    logger.info('System tray created');
  } catch (error) {
    logger.error(`Failed to create tray: ${error}`);
  }
}

// =====================================================
// Scanning Control
// =====================================================

async function startScanning(): Promise<void> {
  try {
    logger.info('เริ่มการสแกน...');
    
    const settings = settingsStore.getSettings();
    
    // Configure services
    signalEngine.updateSettings(settings);
    tieringSystem.updateSettings(settings);
    telegramNotifier.configure(settings.telegram);

    // Load pinned and blacklisted markets
    const pinnedMarkets = settingsStore.getPinnedMarkets();
    const blacklistedMarkets = settingsStore.getBlacklistedMarkets();
    pinnedMarkets.forEach(id => tieringSystem.pinMarket(id));
    blacklistedMarkets.forEach(id => tieringSystem.blacklistMarket(id));

    // Fetch markets from Gamma API
    const markets = await gammaClient.fetchActiveMarkets(
      settings.filters.minLiquidityUsd,
      settings.filters.minVolume24hUsd
    );

    // Filter and add markets
    for (const market of markets) {
      if (tieringSystem.passesFilters(market)) {
        const tier = pinnedMarkets.includes(market.id) ? 'A' : 'B';
        signalEngine.addMarket(market, tier);
      }
    }

    // Start signal engine
    signalEngine.start();

    // Try to connect WebSocket (optional)
    try {
      await wsClient.connect();
    } catch (error) {
      logger.warn('WebSocket connection failed, using REST polling only');
    }

    // Update UI
    sendStatusUpdate();
    
    logger.info(`สแกนเริ่มต้นแล้ว: ${markets.length} ตลาด`);

  } catch (error) {
    logger.error(`Error starting scanning: ${error}`);
    throw error;
  }
}

function stopScanning(): void {
  signalEngine.stop();
  wsClient.disconnect();
  sendStatusUpdate();
  logger.info('หยุดการสแกนแล้ว');
}

// =====================================================
// Event Handlers
// =====================================================

function setupEventHandlers(): void {
  // Signal detected
  signalEngine.on('signal', async (signal: ArbSignal) => {
    // Send to UI
    mainWindow?.webContents.send(IPC_CHANNELS.SIGNAL_DETECTED, signal);

    // Save to log
    const logEntry: SignalLogEntry = {
      id: signal.id,
      timestamp: signal.timestamp,
      marketQuestion: signal.marketQuestion,
      yesAsk: signal.yesAsk,
      noAsk: signal.noAsk,
      gap: signal.effectiveEdge,
      polymarketUrl: signal.polymarketUrl,
      sent: false,
      tier: signal.tier,
    };

    // Send Telegram notification
    const settings = settingsStore.getSettings();
    if (telegramNotifier.isReady()) {
      if (!signal.isLowDepth || settings.general.sendLowDepthAlerts) {
        const result = await telegramNotifier.sendSignalAlert(signal);
        logEntry.sent = result.success;
      }
    }

    settingsStore.addSignalLog(logEntry);
    mainWindow?.webContents.send(IPC_CHANNELS.LOG_UPDATE, logEntry);
  });

  // WebSocket events
  wsClient.on('book', (message) => {
    signalEngine.handleWSBookUpdate(message.asset_id, message.bids, message.asks);
  });

  wsClient.on('connected', () => {
    sendStatusUpdate();
  });

  wsClient.on('disconnected', () => {
    sendStatusUpdate();
  });
}

function sendStatusUpdate(): void {
  const stats = signalEngine.getStats();
  const dashboardStats: DashboardStats = {
    totalMarkets: stats.totalMarkets,
    tierAMarkets: stats.tierAMarkets,
    tierBMarkets: stats.tierBMarkets,
    signalsToday: settingsStore.getSignalLogs().filter(
      l => l.timestamp > Date.now() - 24 * 60 * 60 * 1000
    ).length,
    lastScanTime: Date.now(),
    status: signalEngine.getStats().totalMarkets > 0 ? 'running' : 'paused',
    wsConnected: wsClient.isConnected(),
  };

  mainWindow?.webContents.send(IPC_CHANNELS.STATS_UPDATE, dashboardStats);
}

// =====================================================
// IPC Handlers
// =====================================================

function setupIpcHandlers(): void {
  // Settings
  ipcMain.handle(IPC_CHANNELS.GET_SETTINGS, () => {
    return settingsStore.getSettings();
  });

  ipcMain.handle(IPC_CHANNELS.SAVE_SETTINGS, (_, settings: AppSettings) => {
    settingsStore.saveSettings(settings);
    signalEngine.updateSettings(settings);
    tieringSystem.updateSettings(settings);
    telegramNotifier.configure(settings.telegram);
    return { success: true };
  });

  // Telegram
  ipcMain.handle(IPC_CHANNELS.TEST_TELEGRAM, async () => {
    return telegramNotifier.sendTestMessage();
  });

  // Scanning
  ipcMain.handle(IPC_CHANNELS.START_SCANNING, async () => {
    await startScanning();
    return { success: true };
  });

  ipcMain.handle(IPC_CHANNELS.STOP_SCANNING, () => {
    stopScanning();
    return { success: true };
  });

  // Stats
  ipcMain.handle(IPC_CHANNELS.GET_STATS, () => {
    const stats = signalEngine.getStats();
    return {
      totalMarkets: stats.totalMarkets,
      tierAMarkets: stats.tierAMarkets,
      tierBMarkets: stats.tierBMarkets,
      signalsToday: settingsStore.getSignalLogs().filter(
        l => l.timestamp > Date.now() - 24 * 60 * 60 * 1000
      ).length,
      lastScanTime: Date.now(),
      status: stats.totalMarkets > 0 ? 'running' : 'paused',
      wsConnected: wsClient.isConnected(),
    };
  });

  // Logs
  ipcMain.handle(IPC_CHANNELS.GET_LOGS, (_, limit?: number) => {
    return settingsStore.getSignalLogs(limit);
  });

  ipcMain.handle(IPC_CHANNELS.EXPORT_LOGS, () => {
    return settingsStore.exportLogs();
  });

  // Markets
  ipcMain.handle(IPC_CHANNELS.GET_MARKETS, () => {
    return signalEngine.getMarkets();
  });

  ipcMain.handle(IPC_CHANNELS.PIN_MARKET, (_, marketId: string) => {
    tieringSystem.pinMarket(marketId);
    settingsStore.addPinnedMarket(marketId);
    signalEngine.updateMarketTier(marketId, 'A');
    return { success: true };
  });

  ipcMain.handle(IPC_CHANNELS.UNPIN_MARKET, (_, marketId: string) => {
    tieringSystem.unpinMarket(marketId);
    settingsStore.removePinnedMarket(marketId);
    return { success: true };
  });

  ipcMain.handle(IPC_CHANNELS.BLACKLIST_MARKET, (_, marketId: string) => {
    tieringSystem.blacklistMarket(marketId);
    settingsStore.addBlacklistedMarket(marketId);
    signalEngine.removeMarket(marketId);
    return { success: true };
  });
}

// =====================================================
// App Lifecycle
// =====================================================

app.whenReady().then(() => {
  logger.info('PolyArb Signal กำลังเริ่มต้น...');

  createWindow();
  createTray();
  setupEventHandlers();
  setupIpcHandlers();

  // Auto-start scanning if configured
  const settings = settingsStore.getSettings();
  if (settings.general.startOnBoot) {
    setTimeout(() => startScanning(), 2000);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Don't quit on Windows/Linux when all windows closed
    // App stays in tray
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  stopScanning();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error(`Uncaught exception: ${error}`);
});

process.on('unhandledRejection', (reason) => {
  logger.error(`Unhandled rejection: ${reason}`);
});
