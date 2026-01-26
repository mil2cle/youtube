// =====================================================
// PolyArb Signal - Constants
// =====================================================

// API Endpoints
export const API = {
  GAMMA_BASE: 'https://gamma-api.polymarket.com',
  CLOB_BASE: 'https://clob.polymarket.com',
  WS_CLOB: 'wss://ws-subscriptions-clob.polymarket.com/ws/',
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
    minLiquidityUsd: 5000,
    minVolume24hUsd: 2000,
    maxSpread: 0.03, // 3%
    minTopAskSizeUsd: 100,
  },
  tiering: {
    tierAMax: 50, // max 50 markets in tier A
    tierAIntervalMs: 3000, // 3 seconds
    tierBIntervalMs: 30000, // 30 seconds
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
  GAMMA_MARKETS_PER_10S: 300,
  CLOB_GENERAL_PER_10S: 9000,
  MIN_REQUEST_INTERVAL_MS: 50, // minimum 50ms between requests
  BACKOFF_BASE_MS: 1000,
  BACKOFF_MAX_MS: 30000,
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
