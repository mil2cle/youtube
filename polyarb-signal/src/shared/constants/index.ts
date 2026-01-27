// =====================================================
// PolyArb Signal - Constants
// =====================================================

// API Endpoints
export const API = {
  GAMMA_BASE: 'https://gamma-api.polymarket.com',
  CLOB_BASE: 'https://clob.polymarket.com',
  WS_CLOB: 'wss://ws-subscriptions-clob.polymarket.com/ws/market', // ต้องใช้ /ws/market สำหรับ public market channel
} as const;

// Polymarket URLs
export const POLYMARKET = {
  BASE_URL: 'https://polymarket.com',
  EVENT_URL: (slug: string) => `https://polymarket.com/event/${slug}`,
} as const;

// Default settings
export const DEFAULT_SETTINGS = {
  telegram: {
    botToken: '',
    chatId: '',
  },
  scanning: {
    threshold: 0.01, // 1%
    feeBuffer: 0.002, // 0.2%
    preheatMargin: 0.004, // 0.4%
    debounceMs: 500,
    cooldownMs: 300000, // 5 minutes
    resendDelta: 0.003, // 0.3%
  },
  filters: {
    minLiquidityUsd: 50000, // Increased from 5000 to reduce market count
    minVolume24hUsd: 10000, // Increased from 2000 to reduce market count
    maxSpread: 0.03, // 3%
    minTopAskSizeUsd: 100,
  },
  tiering: {
    tierAMax: 10, // max 10 markets in tier A (reduced further)
    tierAIntervalMs: 10000, // 10 seconds (increased from 5s)
    tierBIntervalMs: 120000, // 120 seconds / 2 minutes (increased from 60s)
    burstMinutes: 10,
    staleMs: 600000, // 10 minutes
    noNearArbWindowMs: 3600000, // 60 minutes
  },
  general: {
    startOnBoot: false,
    minimizeToTray: true,
    sendLowDepthAlerts: false,
  },
} as const;

// Scoring weights for market ranking
export const SCORING_WEIGHTS = {
  VOLUME: 2.2,
  LIQUIDITY: 1.8,
  ACTIVITY: 2.5,
  DEPTH: 1.2,
  NEAR_ARB: 3.0,
  SPREAD_PENALTY: -3.5,
  STALE_PENALTY: -1.0,
} as const;

// Rate limiting
export const RATE_LIMITS = {
  GAMMA_MARKETS_PER_10S: 50,
  CLOB_GENERAL_PER_10S: 30, // Reduced further to avoid rate limiting (was 100)
  MIN_REQUEST_INTERVAL_MS: 500, // Increased to 500ms between requests (was 200ms)
  BACKOFF_BASE_MS: 5000, // Increased backoff
  BACKOFF_MAX_MS: 60000,
  STAGGER_DELAY_MS: 2000, // Delay between starting each market scan
} as const;

// Telegram
export const TELEGRAM = {
  API_BASE: 'https://api.telegram.org/bot',
  MAX_MESSAGE_LENGTH: 4096,
} as const;

// App info
export const APP_INFO = {
  NAME: 'PolyArb Signal',
  VERSION: '1.0.0',
  DESCRIPTION: 'Polymarket Arbitrage Detection Tool',
} as const;
