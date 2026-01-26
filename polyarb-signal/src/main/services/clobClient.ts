// =====================================================
// PolyArb Signal - CLOB API Client
// สำหรับ orderbook และ price data
// =====================================================

import { API, RATE_LIMITS } from '../../shared/constants';
import { Orderbook, OrderbookLevel } from '../../shared/types';
import { logger } from '../utils/logger';

interface ClobBookResponse {
  market: string;
  asset_id: string;
  timestamp: string;
  hash: string;
  bids: { price: string; size: string }[];
  asks: { price: string; size: string }[];
  min_order_size: string;
  tick_size: string;
  neg_risk: boolean;
}

class ClobClient {
  private baseUrl = API.CLOB_BASE;
  private lastRequestTime = 0;
  private requestCount = 0;
  private windowStart = Date.now();

  /**
   * รอให้ผ่าน rate limit ก่อนส่ง request
   */
  private async waitForRateLimit(): Promise<void> {
    const now = Date.now();
    
    // Reset counter ทุก 10 วินาที
    if (now - this.windowStart >= 10000) {
      this.requestCount = 0;
      this.windowStart = now;
    }

    // ถ้าเกิน rate limit ให้รอ
    if (this.requestCount >= RATE_LIMITS.CLOB_GENERAL_PER_10S) {
      const waitTime = 10000 - (now - this.windowStart);
      if (waitTime > 0) {
        logger.debug(`CLOB rate limit reached, waiting ${waitTime}ms`);
        await this.sleep(waitTime);
        this.requestCount = 0;
        this.windowStart = Date.now();
      }
    }

    // รอ minimum interval
    const timeSinceLastRequest = now - this.lastRequestTime;
    if (timeSinceLastRequest < RATE_LIMITS.MIN_REQUEST_INTERVAL_MS) {
      await this.sleep(RATE_LIMITS.MIN_REQUEST_INTERVAL_MS - timeSinceLastRequest);
    }

    this.lastRequestTime = Date.now();
    this.requestCount++;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * ดึง orderbook สำหรับ token
   */
  async getOrderbook(tokenId: string): Promise<Orderbook | null> {
    try {
      await this.waitForRateLimit();

      const url = `${this.baseUrl}/book?token_id=${encodeURIComponent(tokenId)}`;
      const startTime = Date.now();
      
      const response = await fetch(url);
      const latency = Date.now() - startTime;

      if (!response.ok) {
        if (response.status === 429) {
          // Rate limited
          logger.warn('CLOB API rate limited');
          return null;
        }
        if (response.status === 404) {
          // Token not found
          return null;
        }
        throw new Error(`CLOB API error: ${response.status}`);
      }

      const data: ClobBookResponse = await response.json();

      return {
        market: data.market,
        assetId: data.asset_id,
        timestamp: data.timestamp,
        hash: data.hash,
        bids: data.bids,
        asks: data.asks,
        minOrderSize: data.min_order_size,
        tickSize: data.tick_size,
        negRisk: data.neg_risk,
      };
    } catch (error) {
      logger.error(`Error fetching orderbook for ${tokenId}:`, error);
      return null;
    }
  }

  /**
   * ดึง orderbook สำหรับหลาย tokens พร้อมกัน
   */
  async getMultipleOrderbooks(tokenIds: string[]): Promise<Map<string, Orderbook>> {
    const results = new Map<string, Orderbook>();

    // ดึงทีละตัวเพื่อควบคุม rate limit
    for (const tokenId of tokenIds) {
      const orderbook = await this.getOrderbook(tokenId);
      if (orderbook) {
        results.set(tokenId, orderbook);
      }
    }

    return results;
  }

  /**
   * ดึง best ask price จาก orderbook
   */
  getBestAsk(orderbook: Orderbook): { price: number; size: number } | null {
    if (!orderbook.asks || orderbook.asks.length === 0) {
      return null;
    }

    // asks เรียงจากราคาต่ำไปสูง - best ask คือตัวแรก
    const bestAsk = orderbook.asks[0];
    return {
      price: parseFloat(bestAsk.price),
      size: parseFloat(bestAsk.size),
    };
  }

  /**
   * ดึง best bid price จาก orderbook
   */
  getBestBid(orderbook: Orderbook): { price: number; size: number } | null {
    if (!orderbook.bids || orderbook.bids.length === 0) {
      return null;
    }

    // bids เรียงจากราคาสูงไปต่ำ - best bid คือตัวแรก
    const bestBid = orderbook.bids[0];
    return {
      price: parseFloat(bestBid.price),
      size: parseFloat(bestBid.size),
    };
  }

  /**
   * คำนวณ spread จาก orderbook
   */
  getSpread(orderbook: Orderbook): number | null {
    const bestAsk = this.getBestAsk(orderbook);
    const bestBid = this.getBestBid(orderbook);

    if (!bestAsk || !bestBid) {
      return null;
    }

    return bestAsk.price - bestBid.price;
  }

  /**
   * ดึง total depth ที่ best ask (USD size)
   */
  getAskDepth(orderbook: Orderbook, levels: number = 1): number {
    if (!orderbook.asks || orderbook.asks.length === 0) {
      return 0;
    }

    let totalDepth = 0;
    for (let i = 0; i < Math.min(levels, orderbook.asks.length); i++) {
      const ask = orderbook.asks[i];
      totalDepth += parseFloat(ask.size);
    }

    return totalDepth;
  }
}

export const clobClient = new ClobClient();
export default clobClient;
