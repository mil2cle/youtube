// =====================================================
// PolyArb Signal - Signal Engine
// ตรวจจับโอกาส arbitrage และจัดการ alerts
// =====================================================

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import { 
  ParsedMarket, 
  TieredMarket, 
  ArbSignal, 
  Orderbook,
  AppSettings,
  MarketTier 
} from '../../shared/types';
import { DEFAULT_SETTINGS } from '../../shared/constants';
import { clobClient } from './clobClient';
import { logger } from '../utils/logger';

interface MarketState {
  market: TieredMarket;
  yesOrderbook: Orderbook | null;
  noOrderbook: Orderbook | null;
  lastSignalTime: number;
  lastEffectiveEdge: number;
  edgeHistory: { timestamp: number; edge: number }[];
  debounceStart: number | null;
}

class SignalEngine extends EventEmitter {
  private marketStates: Map<string, MarketState> = new Map();
  private settings: AppSettings = DEFAULT_SETTINGS as AppSettings;
  private isRunning = false;
  private scanIntervals: Map<string, ReturnType<typeof setInterval>> = new Map();

  /**
   * อัพเดท settings
   */
  updateSettings(settings: AppSettings): void {
    this.settings = settings;
    logger.info('Signal engine settings updated');
  }

  /**
   * เพิ่มตลาดเข้าสู่ระบบ
   */
  addMarket(market: ParsedMarket, tier: MarketTier = 'B'): void {
    const tieredMarket: TieredMarket = {
      ...market,
      tier,
      score: 0,
      lastUpdate: Date.now(),
      nearArbCount: 0,
      stalePenalty: 0,
      inBurstMode: false,
      burstEndTime: null,
    };

    this.marketStates.set(market.id, {
      market: tieredMarket,
      yesOrderbook: null,
      noOrderbook: null,
      lastSignalTime: 0,
      lastEffectiveEdge: 0,
      edgeHistory: [],
      debounceStart: null,
    });

    logger.debug(`เพิ่มตลาด: ${market.question} (Tier ${tier})`);
  }

  /**
   * ลบตลาดออกจากระบบ
   */
  removeMarket(marketId: string): void {
    const interval = this.scanIntervals.get(marketId);
    if (interval) {
      clearInterval(interval);
      this.scanIntervals.delete(marketId);
    }
    this.marketStates.delete(marketId);
    logger.debug(`ลบตลาด: ${marketId}`);
  }

  /**
   * อัพเดท tier ของตลาด
   */
  updateMarketTier(marketId: string, tier: MarketTier): void {
    const state = this.marketStates.get(marketId);
    if (state) {
      state.market.tier = tier;
      this.restartMarketScan(marketId);
      logger.debug(`อัพเดท tier ตลาด ${marketId} เป็น ${tier}`);
    }
  }

  /**
   * เริ่มการสแกน
   */
  start(): void {
    if (this.isRunning) return;
    
    this.isRunning = true;
    logger.info('Signal engine เริ่มทำงาน');

    // เริ่ม scan ทุกตลาด
    for (const [marketId] of this.marketStates) {
      this.startMarketScan(marketId);
    }

    this.emit('started');
  }

  /**
   * หยุดการสแกน
   */
  stop(): void {
    if (!this.isRunning) return;

    this.isRunning = false;
    
    // หยุด scan ทุกตลาด
    for (const [, interval] of this.scanIntervals) {
      clearInterval(interval);
    }
    this.scanIntervals.clear();

    logger.info('Signal engine หยุดทำงาน');
    this.emit('stopped');
  }

  /**
   * เริ่ม scan ตลาดเดียว
   */
  private startMarketScan(marketId: string): void {
    const state = this.marketStates.get(marketId);
    if (!state || !this.isRunning) return;

    // หยุด interval เดิมถ้ามี
    const existingInterval = this.scanIntervals.get(marketId);
    if (existingInterval) {
      clearInterval(existingInterval);
    }

    // กำหนด interval ตาม tier
    const intervalMs = state.market.tier === 'A' 
      ? this.settings.tiering.tierAIntervalMs 
      : this.settings.tiering.tierBIntervalMs;

    // เพิ่ม jitter ±10%
    const jitter = intervalMs * 0.1 * (Math.random() * 2 - 1);
    const actualInterval = Math.round(intervalMs + jitter);

    // Scan ทันที
    this.scanMarket(marketId);

    // ตั้ง interval
    const interval = setInterval(() => {
      this.scanMarket(marketId);
    }, actualInterval);

    this.scanIntervals.set(marketId, interval);
  }

  /**
   * Restart scan สำหรับตลาด (เมื่อเปลี่ยน tier)
   */
  private restartMarketScan(marketId: string): void {
    if (this.isRunning) {
      this.startMarketScan(marketId);
    }
  }

  /**
   * Scan ตลาดเดียว
   */
  private async scanMarket(marketId: string): Promise<void> {
    const state = this.marketStates.get(marketId);
    if (!state) return;

    try {
      const startTime = Date.now();

      // ดึง orderbook ทั้ง YES และ NO
      const [yesOrderbook, noOrderbook] = await Promise.all([
        clobClient.getOrderbook(state.market.yesTokenId),
        clobClient.getOrderbook(state.market.noTokenId),
      ]);

      const latency = Date.now() - startTime;

      state.yesOrderbook = yesOrderbook;
      state.noOrderbook = noOrderbook;
      state.market.lastUpdate = Date.now();

      // ตรวจสอบ signal
      if (yesOrderbook && noOrderbook) {
        this.checkForSignal(state, latency);
      }

      // อัพเดท stale penalty
      this.updateStalePenalty(state);

    } catch (error) {
      logger.error(`Error scanning market ${marketId}:`, error);
    }
  }

  /**
   * ตรวจสอบว่ามี arbitrage signal หรือไม่
   */
  private checkForSignal(state: MarketState, latencyMs: number): void {
    const yesAsk = clobClient.getBestAsk(state.yesOrderbook!);
    const noAsk = clobClient.getBestAsk(state.noOrderbook!);

    if (!yesAsk || !noAsk) {
      state.debounceStart = null;
      return;
    }

    // คำนวณ effective edge
    const sumCost = yesAsk.price + noAsk.price;
    const effectiveEdge = 1.0 - (sumCost + this.settings.scanning.feeBuffer);

    // เก็บ history
    state.edgeHistory.push({ timestamp: Date.now(), edge: effectiveEdge });
    // เก็บแค่ 30 วินาทีล่าสุด
    const cutoff = Date.now() - 30000;
    state.edgeHistory = state.edgeHistory.filter(h => h.timestamp > cutoff);

    // ตรวจสอบ preheat (ใกล้ threshold)
    const preheatThreshold = this.settings.scanning.threshold - this.settings.scanning.preheatMargin;
    if (effectiveEdge >= preheatThreshold && state.market.tier === 'B') {
      this.promoteToTierA(state);
    }

    // ตรวจสอบว่าเข้าเงื่อนไข signal หรือไม่
    if (effectiveEdge >= this.settings.scanning.threshold) {
      // Debounce check
      if (state.debounceStart === null) {
        state.debounceStart = Date.now();
      }

      const debounceElapsed = Date.now() - state.debounceStart;
      if (debounceElapsed >= this.settings.scanning.debounceMs) {
        // ตรวจสอบ cooldown
        const cooldownPassed = Date.now() - state.lastSignalTime >= this.settings.scanning.cooldownMs;
        const edgeIncreased = effectiveEdge >= state.lastEffectiveEdge + this.settings.scanning.resendDelta;

        if (cooldownPassed || edgeIncreased) {
          this.emitSignal(state, yesAsk, noAsk, effectiveEdge, latencyMs);
          state.lastSignalTime = Date.now();
          state.lastEffectiveEdge = effectiveEdge;
          state.market.nearArbCount++;
        }
      }
    } else {
      state.debounceStart = null;
    }
  }

  /**
   * ส่ง signal event
   */
  private emitSignal(
    state: MarketState, 
    yesAsk: { price: number; size: number },
    noAsk: { price: number; size: number },
    effectiveEdge: number,
    latencyMs: number
  ): void {
    const signal: ArbSignal = {
      id: uuidv4(),
      marketId: state.market.id,
      marketQuestion: state.market.question,
      marketSlug: state.market.slug,
      polymarketUrl: state.market.polymarketUrl,
      yesAsk: yesAsk.price,
      noAsk: noAsk.price,
      sumCost: yesAsk.price + noAsk.price,
      effectiveEdge,
      threshold: this.settings.scanning.threshold,
      feeBuffer: this.settings.scanning.feeBuffer,
      yesAskDepth: yesAsk.size,
      noAskDepth: noAsk.size,
      timestamp: Date.now(),
      latencyMs,
      tier: state.market.tier,
      isLowDepth: yesAsk.size < this.settings.filters.minTopAskSizeUsd || 
                  noAsk.size < this.settings.filters.minTopAskSizeUsd,
    };

    logger.info(`🎯 Signal detected: ${state.market.question} - Edge: ${(effectiveEdge * 100).toFixed(2)}%`);
    this.emit('signal', signal);
  }

  /**
   * Promote ตลาดขึ้น Tier A
   */
  private promoteToTierA(state: MarketState): void {
    if (state.market.tier === 'A') return;

    state.market.tier = 'A';
    state.market.inBurstMode = true;
    state.market.burstEndTime = Date.now() + (this.settings.tiering.burstMinutes * 60 * 1000);
    
    this.restartMarketScan(state.market.id);
    logger.info(`📈 Promoted to Tier A: ${state.market.question}`);
    this.emit('tier_change', { marketId: state.market.id, tier: 'A' });
  }

  /**
   * Demote ตลาดลง Tier B
   */
  private demoteToTierB(state: MarketState): void {
    if (state.market.tier === 'B') return;
    if (state.market.inBurstMode && state.market.burstEndTime && Date.now() < state.market.burstEndTime) {
      return; // ยังอยู่ใน burst mode
    }

    state.market.tier = 'B';
    state.market.inBurstMode = false;
    state.market.burstEndTime = null;
    
    this.restartMarketScan(state.market.id);
    logger.info(`📉 Demoted to Tier B: ${state.market.question}`);
    this.emit('tier_change', { marketId: state.market.id, tier: 'B' });
  }

  /**
   * อัพเดท stale penalty
   */
  private updateStalePenalty(state: MarketState): void {
    const timeSinceUpdate = Date.now() - state.market.lastUpdate;
    
    if (timeSinceUpdate > this.settings.tiering.staleMs) {
      state.market.stalePenalty = Math.min(state.market.stalePenalty + 0.1, 1.0);
      
      // ถ้า stale นานเกินไป demote
      if (state.market.tier === 'A' && !state.market.inBurstMode) {
        this.demoteToTierB(state);
      }
    } else {
      state.market.stalePenalty = Math.max(state.market.stalePenalty - 0.05, 0);
    }
  }

  /**
   * รับ orderbook update จาก WebSocket
   */
  handleWSBookUpdate(assetId: string, bids: { price: string; size: string }[], asks: { price: string; size: string }[]): void {
    // หาตลาดที่มี asset นี้
    for (const [, state] of this.marketStates) {
      if (state.market.yesTokenId === assetId) {
        state.yesOrderbook = {
          market: state.market.conditionId,
          assetId,
          timestamp: Date.now().toString(),
          hash: '',
          bids,
          asks,
          minOrderSize: '0.01',
          tickSize: '0.01',
          negRisk: false,
        };
        state.market.lastUpdate = Date.now();
        this.checkForSignal(state, 0);
        break;
      }
      if (state.market.noTokenId === assetId) {
        state.noOrderbook = {
          market: state.market.conditionId,
          assetId,
          timestamp: Date.now().toString(),
          hash: '',
          bids,
          asks,
          minOrderSize: '0.01',
          tickSize: '0.01',
          negRisk: false,
        };
        state.market.lastUpdate = Date.now();
        this.checkForSignal(state, 0);
        break;
      }
    }
  }

  /**
   * รับสถิติ
   */
  getStats(): { totalMarkets: number; tierAMarkets: number; tierBMarkets: number } {
    let tierA = 0;
    let tierB = 0;

    for (const [, state] of this.marketStates) {
      if (state.market.tier === 'A') tierA++;
      else tierB++;
    }

    return {
      totalMarkets: this.marketStates.size,
      tierAMarkets: tierA,
      tierBMarkets: tierB,
    };
  }

  /**
   * รับรายการตลาดทั้งหมด
   */
  getMarkets(): TieredMarket[] {
    return Array.from(this.marketStates.values()).map(s => s.market);
  }
}

export const signalEngine = new SignalEngine();
export default signalEngine;
