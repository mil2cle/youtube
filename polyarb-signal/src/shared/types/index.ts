// =====================================================
// PolyArb Signal - Shared Types
// =====================================================

// Market data from Gamma API
export interface GammaMarket {
  id: string;
  question: string;
  conditionId: string;
  slug: string;
  outcomes: string;
  outcomePrices: string;
  volume: string;
  volumeNum: number;
  volume24hr: number;
  liquidityNum: number;
  active: boolean;
  closed: boolean;
  clobTokenIds: string;
  acceptingOrders: boolean;
  enableOrderBook: boolean;
  endDate: string;
  category: string;
}

// Parsed market with token IDs
export interface ParsedMarket {
  id: string;
  question: string;
  slug: string;
  conditionId: string;
  yesTokenId: string;
  noTokenId: string;
  volume24h: number;
  liquidity: number;
  active: boolean;
  closed: boolean;
  acceptingOrders: boolean;
  category: string;
  endDate: string;
  polymarketUrl: string;
}

// Orderbook data from CLOB API
export interface OrderbookLevel {
  price: string;
  size: string;
}

export interface Orderbook {
  market: string;
  assetId: string;
  timestamp: string;
  hash: string;
  bids: OrderbookLevel[];
  asks: OrderbookLevel[];
  minOrderSize: string;
  tickSize: string;
  negRisk: boolean;
}

// Signal data
export interface ArbSignal {
  id: string;
  marketId: string;
  marketQuestion: string;
  marketSlug: string;
  polymarketUrl: string;
  yesAsk: number;
  noAsk: number;
  sumCost: number;
  effectiveEdge: number;
  threshold: number;
  feeBuffer: number;
  yesAskDepth: number;
  noAskDepth: number;
  timestamp: number;
  latencyMs: number;
  tier: MarketTier;
  isLowDepth: boolean;
}

// Market tier for scanning priority
export type MarketTier = 'A' | 'B';

// Market with tier and metrics
export interface TieredMarket extends ParsedMarket {
  tier: MarketTier;
  score: number;
  lastUpdate: number;
  nearArbCount: number;
  stalePenalty: number;
  inBurstMode: boolean;
  burstEndTime: number | null;
}

// WebSocket message types
export interface WSBookMessage {
  event_type: 'book';
  asset_id: string;
  market: string;
  bids: { price: string; size: string }[];
  asks: { price: string; size: string }[];
  timestamp: string;
  hash: string;
}

export interface WSPriceChangeMessage {
  event_type: 'price_change';
  market: string;
  price_changes: {
    asset_id: string;
    price: string;
    size: string;
    side: 'BUY' | 'SELL';
    best_bid: string;
    best_ask: string;
  }[];
  timestamp: string;
}

export type WSMessage = WSBookMessage | WSPriceChangeMessage;

// Settings
export interface AppSettings {
  telegram: {
    botToken: string;
    chatId: string;
  };
  scanning: {
    threshold: number; // default 0.01 (1%)
    feeBuffer: number; // default 0.002 (0.2%)
    preheatMargin: number; // default 0.004
    debounceMs: number; // default 500
    cooldownMs: number; // default 300000 (5 min)
    resendDelta: number; // default 0.003
  };
  filters: {
    minLiquidityUsd: number; // default 5000
    minVolume24hUsd: number; // default 2000
    maxSpread: number; // default 0.03
    minTopAskSizeUsd: number; // default 100
  };
  tiering: {
    tierAMax: number; // max markets in tier A
    tierAIntervalMs: number; // default 3000 (3s)
    tierBIntervalMs: number; // default 30000 (30s)
    burstMinutes: number; // default 10
    staleMs: number; // default 600000 (10 min)
    noNearArbWindowMs: number; // default 3600000 (60 min)
  };
  general: {
    startOnBoot: boolean;
    minimizeToTray: boolean;
    sendLowDepthAlerts: boolean;
  };
}

// Dashboard stats
export interface DashboardStats {
  totalMarkets: number;
  tierAMarkets: number;
  tierBMarkets: number;
  signalsToday: number;
  lastScanTime: number;
  status: AppStatus;
  wsConnected: boolean;
}

export type AppStatus = 'running' | 'paused' | 'error' | 'starting';

// Signal log entry for UI
export interface SignalLogEntry {
  id: string;
  timestamp: number;
  marketQuestion: string;
  yesAsk: number;
  noAsk: number;
  gap: number;
  polymarketUrl: string;
  sent: boolean;
  tier: MarketTier;
}

// WebSocket status info
export interface WSStatusInfo {
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'degraded' | 'error';
  message: string;
  messagesReceived: number;
  lastMessageTime: number | null;
  reconnectAttempts: number;
  subscribedAssets: number;
}

// IPC channel names
export const IPC_CHANNELS = {
  // Main -> Renderer
  SIGNAL_DETECTED: 'signal:detected',
  STATS_UPDATE: 'stats:update',
  LOG_UPDATE: 'log:update',
  STATUS_CHANGE: 'status:change',
  WS_STATUS_UPDATE: 'ws:status:update',
  
  // Renderer -> Main
  GET_SETTINGS: 'settings:get',
  SAVE_SETTINGS: 'settings:save',
  TEST_TELEGRAM: 'telegram:test',
  TEST_WEBSOCKET: 'websocket:test',
  GET_WS_STATUS: 'websocket:status',
  START_SCANNING: 'scanning:start',
  STOP_SCANNING: 'scanning:stop',
  GET_STATS: 'stats:get',
  GET_LOGS: 'logs:get',
  EXPORT_LOGS: 'logs:export',
  GET_MARKETS: 'markets:get',
  PIN_MARKET: 'market:pin',
  UNPIN_MARKET: 'market:unpin',
  BLACKLIST_MARKET: 'market:blacklist',
} as const;
