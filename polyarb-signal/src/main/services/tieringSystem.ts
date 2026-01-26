// =====================================================
// PolyArb Signal - Market Tiering System
// จัดลำดับความสำคัญของตลาดตาม scoring
// =====================================================

import { ParsedMarket, TieredMarket, MarketTier, AppSettings } from '../../shared/types';
import { SCORING_WEIGHTS, DEFAULT_SETTINGS } from '../../shared/constants';
import { logger } from '../utils/logger';

interface MarketMetrics {
  volume24h: number;
  liquidity: number;
  spread: number;
  depth: number;
  nearArbCount: number;
  stalePenalty: number;
}

class TieringSystem {
  private settings: AppSettings = DEFAULT_SETTINGS as AppSettings;
  private pinnedMarkets: Set<string> = new Set();
  private blacklistedMarkets: Set<string> = new Set();

  /**
   * อัพเดท settings
   */
  updateSettings(settings: AppSettings): void {
    this.settings = settings;
  }

  /**
   * คำนวณ score สำหรับตลาด
   */
  calculateScore(market: ParsedMarket, metrics: MarketMetrics): number {
    // Normalize values (0-1 scale)
    const volumeScore = Math.min(metrics.volume24h / 100000, 1); // max 100k
    const liquidityScore = Math.min(metrics.liquidity / 50000, 1); // max 50k
    const depthScore = Math.min(metrics.depth / 1000, 1); // max 1000
    const nearArbScore = Math.min(metrics.nearArbCount / 10, 1); // max 10 signals
    const spreadPenalty = Math.min(metrics.spread / 0.1, 1); // max 10% spread
    const stalePenalty = metrics.stalePenalty;

    // Calculate weighted score
    const score = 
      (volumeScore * SCORING_WEIGHTS.VOLUME) +
      (liquidityScore * SCORING_WEIGHTS.LIQUIDITY) +
      (depthScore * SCORING_WEIGHTS.DEPTH) +
      (nearArbScore * SCORING_WEIGHTS.NEAR_ARB) +
      (spreadPenalty * SCORING_WEIGHTS.SPREAD_PENALTY) +
      (stalePenalty * SCORING_WEIGHTS.STALE_PENALTY);

    return Math.max(0, score);
  }

  /**
   * จัด tier ให้ตลาดทั้งหมด
   */
  assignTiers(markets: TieredMarket[]): TieredMarket[] {
    // Filter out blacklisted markets
    const eligibleMarkets = markets.filter(m => !this.blacklistedMarkets.has(m.id));

    // Sort by score descending
    eligibleMarkets.sort((a, b) => b.score - a.score);

    // Assign tiers
    const tierAMax = this.settings.tiering.tierAMax;
    const result: TieredMarket[] = [];

    for (let i = 0; i < eligibleMarkets.length; i++) {
      const market = eligibleMarkets[i];
      
      // Pinned markets always go to Tier A
      if (this.pinnedMarkets.has(market.id)) {
        market.tier = 'A';
      }
      // Markets in burst mode stay in Tier A
      else if (market.inBurstMode && market.burstEndTime && Date.now() < market.burstEndTime) {
        market.tier = 'A';
      }
      // Top N markets go to Tier A
      else if (i < tierAMax) {
        market.tier = 'A';
      }
      // Rest go to Tier B
      else {
        market.tier = 'B';
      }

      result.push(market);
    }

    logger.debug(`Tier assignment: ${result.filter(m => m.tier === 'A').length} Tier A, ${result.filter(m => m.tier === 'B').length} Tier B`);
    return result;
  }

  /**
   * ตรวจสอบว่าตลาดผ่านเกณฑ์ filter หรือไม่
   */
  passesFilters(market: ParsedMarket): boolean {
    // Check blacklist
    if (this.blacklistedMarkets.has(market.id)) {
      return false;
    }

    // Check liquidity
    if (market.liquidity < this.settings.filters.minLiquidityUsd) {
      return false;
    }

    // Check volume
    if (market.volume24h < this.settings.filters.minVolume24hUsd) {
      return false;
    }

    // Check active status
    if (!market.active || market.closed || !market.acceptingOrders) {
      return false;
    }

    return true;
  }

  /**
   * Pin ตลาดให้อยู่ Tier A เสมอ
   */
  pinMarket(marketId: string): void {
    this.pinnedMarkets.add(marketId);
    logger.info(`Pinned market: ${marketId}`);
  }

  /**
   * Unpin ตลาด
   */
  unpinMarket(marketId: string): void {
    this.pinnedMarkets.delete(marketId);
    logger.info(`Unpinned market: ${marketId}`);
  }

  /**
   * Blacklist ตลาด
   */
  blacklistMarket(marketId: string): void {
    this.blacklistedMarkets.add(marketId);
    this.pinnedMarkets.delete(marketId); // Remove from pinned if present
    logger.info(`Blacklisted market: ${marketId}`);
  }

  /**
   * Remove from blacklist
   */
  unblacklistMarket(marketId: string): void {
    this.blacklistedMarkets.delete(marketId);
    logger.info(`Removed from blacklist: ${marketId}`);
  }

  /**
   * รับรายการ pinned markets
   */
  getPinnedMarkets(): string[] {
    return Array.from(this.pinnedMarkets);
  }

  /**
   * รับรายการ blacklisted markets
   */
  getBlacklistedMarkets(): string[] {
    return Array.from(this.blacklistedMarkets);
  }

  /**
   * ตรวจสอบว่าตลาดควรเข้า burst mode หรือไม่
   */
  shouldEnterBurstMode(market: TieredMarket, currentEdge: number): boolean {
    const preheatThreshold = this.settings.scanning.threshold - this.settings.scanning.preheatMargin;
    return currentEdge >= preheatThreshold && market.tier === 'B';
  }

  /**
   * ตรวจสอบว่าตลาดควรออกจาก burst mode หรือไม่
   */
  shouldExitBurstMode(market: TieredMarket): boolean {
    if (!market.inBurstMode) return false;
    if (!market.burstEndTime) return true;
    return Date.now() >= market.burstEndTime;
  }

  /**
   * ตรวจสอบว่าตลาดควร demote หรือไม่
   */
  shouldDemote(market: TieredMarket): boolean {
    // Don't demote pinned markets
    if (this.pinnedMarkets.has(market.id)) {
      return false;
    }

    // Don't demote markets in burst mode
    if (market.inBurstMode && market.burstEndTime && Date.now() < market.burstEndTime) {
      return false;
    }

    // Demote if no near-arb signals in the window
    const noNearArbWindow = this.settings.tiering.noNearArbWindowMs;
    const timeSinceLastSignal = Date.now() - market.lastUpdate;
    
    if (market.nearArbCount === 0 && timeSinceLastSignal > noNearArbWindow) {
      return true;
    }

    return false;
  }
}

export const tieringSystem = new TieringSystem();
export default tieringSystem;
