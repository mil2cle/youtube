// =====================================================
// PolyArb Signal - Gamma API Client
// สำหรับ market discovery และ metadata
// =====================================================

import { API, RATE_LIMITS } from '../../shared/constants';
import { GammaMarket, ParsedMarket } from '../../shared/types';
import { logger } from '../utils/logger';

class GammaClient {
  private baseUrl = API.GAMMA_BASE;
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
    if (this.requestCount >= RATE_LIMITS.GAMMA_MARKETS_PER_10S) {
      const waitTime = 10000 - (now - this.windowStart);
      if (waitTime > 0) {
        logger.debug(`Rate limit reached, waiting ${waitTime}ms`);
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
   * ดึงรายการตลาดทั้งหมดที่ active
   */
  async fetchActiveMarkets(
    minLiquidity: number = 5000,
    minVolume24h: number = 2000,
    limit: number = 100
  ): Promise<ParsedMarket[]> {
    const allMarkets: ParsedMarket[] = [];
    let offset = 0;
    let hasMore = true;

    logger.info('เริ่มดึงข้อมูลตลาดจาก Gamma API...');

    while (hasMore) {
      try {
        await this.waitForRateLimit();

        const params = new URLSearchParams({
          active: 'true',
          closed: 'false',
          limit: limit.toString(),
          offset: offset.toString(),
          order: 'volume24hr',
          ascending: 'false',
        });

        // เพิ่ม filter ถ้ามี
        if (minLiquidity > 0) {
          params.append('liquidity_num_min', minLiquidity.toString());
        }
        if (minVolume24h > 0) {
          params.append('volume_num_min', minVolume24h.toString());
        }

        const url = `${this.baseUrl}/markets?${params.toString()}`;
        logger.debug(`Fetching: ${url}`);

        const response = await fetch(url);
        
        if (!response.ok) {
          if (response.status === 429) {
            // Rate limited - exponential backoff
            const backoffTime = Math.min(
              RATE_LIMITS.BACKOFF_BASE_MS * Math.pow(2, Math.floor(this.requestCount / 100)),
              RATE_LIMITS.BACKOFF_MAX_MS
            );
            logger.warn(`Rate limited, backing off for ${backoffTime}ms`);
            await this.sleep(backoffTime);
            continue;
          }
          throw new Error(`Gamma API error: ${response.status} ${response.statusText}`);
        }

        const markets = (await response.json()) as GammaMarket[];

        if (markets.length === 0) {
          hasMore = false;
          break;
        }

        // Parse และ filter ตลาด binary (YES/NO) เท่านั้น
        for (const market of markets) {
          const parsed = this.parseMarket(market);
          if (parsed) {
            allMarkets.push(parsed);
          }
        }

        offset += limit;
        
        // ถ้าได้น้อยกว่า limit แสดงว่าหมดแล้ว
        if (markets.length < limit) {
          hasMore = false;
        }

        logger.debug(`ดึงได้ ${markets.length} ตลาด, รวม ${allMarkets.length} ตลาด binary`);

      } catch (error) {
        logger.error('Error fetching markets:', error);
        throw error;
      }
    }

    logger.info(`ดึงข้อมูลตลาดเสร็จ: ${allMarkets.length} ตลาด binary`);
    return allMarkets;
  }

  /**
   * ดึงข้อมูลตลาดเดียวจาก slug
   */
  async fetchMarketBySlug(slug: string): Promise<ParsedMarket | null> {
    try {
      await this.waitForRateLimit();

      const url = `${this.baseUrl}/markets?slug=${encodeURIComponent(slug)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Gamma API error: ${response.status}`);
      }

      const markets = (await response.json()) as GammaMarket[];
      
      if (markets.length === 0) {
        return null;
      }

      return this.parseMarket(markets[0]);
    } catch (error) {
      logger.error(`Error fetching market ${slug}:`, error);
      return null;
    }
  }

  /**
   * Parse market data จาก Gamma API response
   * คืน null ถ้าไม่ใช่ binary market (YES/NO)
   */
  private parseMarket(market: GammaMarket): ParsedMarket | null {
    try {
      // Parse outcomes - ต้องเป็น YES/NO เท่านั้น
      const outcomes = JSON.parse(market.outcomes || '[]') as string[];
      if (!Array.isArray(outcomes) || outcomes.length !== 2) {
        return null;
      }

      // ตรวจสอบว่าเป็น YES/NO
      const hasYes = outcomes.some((o: string) => o.toLowerCase() === 'yes');
      const hasNo = outcomes.some((o: string) => o.toLowerCase() === 'no');
      if (!hasYes || !hasNo) {
        return null;
      }

      // Parse token IDs
      const tokenIds = JSON.parse(market.clobTokenIds || '[]') as string[];
      if (!Array.isArray(tokenIds) || tokenIds.length !== 2) {
        return null;
      }

      // ตรวจสอบว่า orderbook enabled และ accepting orders
      if (!market.enableOrderBook || !market.acceptingOrders) {
        return null;
      }

      // หา YES และ NO token IDs (YES มักจะเป็นตัวแรก)
      const yesIndex = outcomes.findIndex((o: string) => o.toLowerCase() === 'yes');
      const noIndex = outcomes.findIndex((o: string) => o.toLowerCase() === 'no');

      return {
        id: market.id,
        question: market.question,
        slug: market.slug,
        conditionId: market.conditionId,
        yesTokenId: tokenIds[yesIndex],
        noTokenId: tokenIds[noIndex],
        volume24h: market.volume24hr || 0,
        liquidity: market.liquidityNum || 0,
        active: market.active,
        closed: market.closed,
        acceptingOrders: market.acceptingOrders,
        category: market.category || 'Unknown',
        endDate: market.endDate,
        polymarketUrl: `https://polymarket.com/event/${market.slug}`,
      };
    } catch (error) {
      logger.debug(`Failed to parse market ${market.id}:`, error);
      return null;
    }
  }
}

export const gammaClient = new GammaClient();
export default gammaClient;
