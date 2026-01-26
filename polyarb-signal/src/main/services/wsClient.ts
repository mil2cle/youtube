// =====================================================
// PolyArb Signal - WebSocket Client
// สำหรับ real-time orderbook updates
// =====================================================

import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { API } from '../../shared/constants';
import { WSMessage, WSBookMessage, WSPriceChangeMessage } from '../../shared/types';
import { logger } from '../utils/logger';

interface WSSubscription {
  type: 'subscribe' | 'unsubscribe';
  channel: 'market';
  assets_ids: string[];
}

class WebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private url = API.WS_CLOB;
  private subscribedAssets: Set<string> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private pingInterval: NodeJS.Timeout | null = null;
  private isConnecting = false;
  private shouldReconnect = true;

  /**
   * เชื่อมต่อ WebSocket
   */
  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.shouldReconnect = true;

    return new Promise((resolve, reject) => {
      try {
        logger.info('กำลังเชื่อมต่อ WebSocket...');
        
        this.ws = new WebSocket(this.url);

        this.ws.on('open', () => {
          logger.info('WebSocket เชื่อมต่อสำเร็จ');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.startPingInterval();
          
          // Re-subscribe to previously subscribed assets
          if (this.subscribedAssets.size > 0) {
            this.subscribeToAssets(Array.from(this.subscribedAssets));
          }
          
          this.emit('connected');
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          try {
            const message = JSON.parse(data.toString()) as WSMessage;
            this.handleMessage(message);
          } catch (error) {
            logger.error('Error parsing WebSocket message:', error);
          }
        });

        this.ws.on('close', (code, reason) => {
          logger.warn(`WebSocket ปิดการเชื่อมต่อ: ${code} - ${reason}`);
          this.isConnecting = false;
          this.stopPingInterval();
          this.emit('disconnected');
          
          if (this.shouldReconnect) {
            this.attemptReconnect();
          }
        });

        this.ws.on('error', (error) => {
          logger.error('WebSocket error:', error);
          this.isConnecting = false;
          this.emit('error', error);
          
          if (this.reconnectAttempts === 0) {
            reject(error);
          }
        });

        this.ws.on('pong', () => {
          logger.debug('WebSocket pong received');
        });

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * ปิดการเชื่อมต่อ
   */
  disconnect(): void {
    this.shouldReconnect = false;
    this.stopPingInterval();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.subscribedAssets.clear();
    logger.info('WebSocket ปิดการเชื่อมต่อแล้ว');
  }

  /**
   * Subscribe to market updates for specific assets
   */
  subscribeToAssets(assetIds: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      logger.warn('WebSocket not connected, queuing subscription');
      assetIds.forEach(id => this.subscribedAssets.add(id));
      return;
    }

    const subscription: WSSubscription = {
      type: 'subscribe',
      channel: 'market',
      assets_ids: assetIds,
    };

    this.ws.send(JSON.stringify(subscription));
    assetIds.forEach(id => this.subscribedAssets.add(id));
    logger.debug(`Subscribed to ${assetIds.length} assets`);
  }

  /**
   * Unsubscribe from market updates
   */
  unsubscribeFromAssets(assetIds: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      assetIds.forEach(id => this.subscribedAssets.delete(id));
      return;
    }

    const subscription: WSSubscription = {
      type: 'unsubscribe',
      channel: 'market',
      assets_ids: assetIds,
    };

    this.ws.send(JSON.stringify(subscription));
    assetIds.forEach(id => this.subscribedAssets.delete(id));
    logger.debug(`Unsubscribed from ${assetIds.length} assets`);
  }

  /**
   * ตรวจสอบสถานะการเชื่อมต่อ
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * จัดการ message ที่ได้รับ
   */
  private handleMessage(message: WSMessage): void {
    switch (message.event_type) {
      case 'book':
        this.emit('book', message as WSBookMessage);
        break;
      case 'price_change':
        this.emit('price_change', message as WSPriceChangeMessage);
        break;
      default:
        logger.debug('Unknown message type:', (message as any).event_type);
    }
  }

  /**
   * พยายามเชื่อมต่อใหม่
   */
  private async attemptReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      logger.error('Max reconnect attempts reached');
      this.emit('max_reconnect_reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    const jitter = Math.random() * 1000;
    const totalDelay = Math.min(delay + jitter, 30000);

    logger.info(`พยายามเชื่อมต่อใหม่ครั้งที่ ${this.reconnectAttempts} ใน ${Math.round(totalDelay)}ms`);
    
    await this.sleep(totalDelay);
    
    try {
      await this.connect();
    } catch (error) {
      logger.error('Reconnect failed:', error);
    }
  }

  /**
   * เริ่ม ping interval เพื่อ keep-alive
   */
  private startPingInterval(): void {
    this.stopPingInterval();
    
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.ping();
      }
    }, 30000); // ping ทุก 30 วินาที
  }

  /**
   * หยุด ping interval
   */
  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export const wsClient = new WebSocketClient();
export default wsClient;
