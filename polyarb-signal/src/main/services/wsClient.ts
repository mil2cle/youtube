// =====================================================
// PolyArb Signal - WebSocket Client
// สำหรับ real-time orderbook updates
// ตาม Polymarket CLOB WebSocket docs
// =====================================================

import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { API, RATE_LIMITS } from '../../shared/constants';
import { WSBookMessage, WSPriceChangeMessage } from '../../shared/types';
import { logger } from '../utils/logger';

// Subscribe message format ตาม Polymarket docs
interface WSInitialSubscribe {
  assets_ids: string[];
  type: 'market';
}

interface WSSubscribeOperation {
  assets_ids: string[];
  operation: 'subscribe' | 'unsubscribe';
}

// Raw message from WebSocket
interface RawWSMessage {
  event_type?: string;
  asset_id?: string;
  market?: string;
  bids?: { price: string; size: string }[];
  asks?: { price: string; size: string }[];
  timestamp?: string;
  hash?: string;
  price_changes?: unknown[];
}

// Connection status for UI
export type WSConnectionStatus = 
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'degraded'  // fallback to REST polling
  | 'error';

export interface WSStatusInfo {
  status: WSConnectionStatus;
  message: string;
  messagesReceived: number;
  lastMessageTime: number | null;
  reconnectAttempts: number;
  subscribedAssets: number;
}

class WebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private url = API.WS_CLOB;
  private subscribedAssets: Set<string> = new Set();
  private pendingSubscriptions: Set<string> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private staleCheckInterval: ReturnType<typeof setInterval> | null = null;
  private subscriptionBatchTimeout: ReturnType<typeof setTimeout> | null = null;
  private isConnecting = false;
  private shouldReconnect = true;
  private connectionStatus: WSConnectionStatus = 'disconnected';
  private statusMessage = 'ยังไม่ได้เชื่อมต่อ';
  private messagesReceived = 0;
  private lastMessageTime: number | null = null;
  private isInitialConnection = true;

  /**
   * เชื่อมต่อ WebSocket
   */
  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.shouldReconnect = true;
    this.updateStatus('connecting', 'กำลังเชื่อมต่อ...');

    return new Promise((resolve, reject) => {
      try {
        logger.info(`กำลังเชื่อมต่อ WebSocket: ${this.url}`);
        
        this.ws = new WebSocket(this.url);

        // Set timeout for connection
        const connectionTimeout = setTimeout(() => {
          if (this.isConnecting) {
            this.ws?.close();
            this.isConnecting = false;
            this.updateStatus('error', 'Connection timeout');
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

        this.ws.on('open', () => {
          clearTimeout(connectionTimeout);
          logger.info('✅ WebSocket เชื่อมต่อสำเร็จ');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.updateStatus('connected', 'เชื่อมต่อแล้ว');
          this.startPingInterval();
          this.startStaleCheck();
          
          // Send initial subscription if we have pending assets
          if (this.subscribedAssets.size > 0 || this.pendingSubscriptions.size > 0) {
            const allAssets = new Set([...this.subscribedAssets, ...this.pendingSubscriptions]);
            this.sendInitialSubscription(Array.from(allAssets));
            this.pendingSubscriptions.clear();
          }
          
          this.isInitialConnection = false;
          this.emit('connected');
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          try {
            const message = JSON.parse(data.toString()) as RawWSMessage;
            this.messagesReceived++;
            this.lastMessageTime = Date.now();
            this.handleMessage(message);
          } catch (error) {
            logger.error('Error parsing WebSocket message:', error);
          }
        });

        this.ws.on('close', (code, reason) => {
          clearTimeout(connectionTimeout);
          const reasonStr = reason?.toString() || 'unknown';
          logger.warn(`WebSocket ปิดการเชื่อมต่อ: code=${code}, reason=${reasonStr}`);
          this.isConnecting = false;
          this.stopPingInterval();
          this.stopStaleCheck();
          
          // Determine status message based on close code
          let statusMsg = `ปิดการเชื่อมต่อ (code: ${code})`;
          if (code === 1006) {
            statusMsg = 'การเชื่อมต่อถูกตัด (network issue)';
          } else if (code === 404 || code === 1002) {
            statusMsg = 'Endpoint ไม่ถูกต้อง';
          }
          
          this.updateStatus('disconnected', statusMsg);
          this.emit('disconnected');
          
          if (this.shouldReconnect) {
            this.attemptReconnect();
          }
        });

        this.ws.on('error', (error: Error) => {
          clearTimeout(connectionTimeout);
          logger.error('WebSocket error:', error.message);
          this.isConnecting = false;
          
          // Parse error message for better status
          let statusMsg = error.message;
          if (error.message.includes('404')) {
            statusMsg = 'Endpoint ไม่พบ (404) - ตรวจสอบ URL';
          } else if (error.message.includes('ECONNREFUSED')) {
            statusMsg = 'ไม่สามารถเชื่อมต่อได้ (connection refused)';
          } else if (error.message.includes('ETIMEDOUT')) {
            statusMsg = 'Connection timeout';
          }
          
          this.updateStatus('error', statusMsg);
          this.emit('error', error);
          
          if (this.isInitialConnection) {
            reject(error);
          }
        });

        this.ws.on('pong', () => {
          logger.debug('WebSocket pong received');
        });

      } catch (error) {
        this.isConnecting = false;
        this.updateStatus('error', `Connection error: ${error}`);
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
    this.stopStaleCheck();
    this.clearSubscriptionBatch();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.subscribedAssets.clear();
    this.pendingSubscriptions.clear();
    this.updateStatus('disconnected', 'ปิดการเชื่อมต่อแล้ว');
    logger.info('WebSocket ปิดการเชื่อมต่อแล้ว');
  }

  /**
   * ส่ง initial subscription ตาม Polymarket docs
   * Format: { "assets_ids": ["tokenId1", "tokenId2"], "type": "market" }
   */
  private sendInitialSubscription(assetIds: string[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || assetIds.length === 0) {
      return;
    }

    const subscription: WSInitialSubscribe = {
      assets_ids: assetIds,
      type: 'market',
    };

    logger.info(`📤 Sending initial subscription for ${assetIds.length} assets`);
    logger.debug(`Token IDs: ${assetIds.slice(0, 5).join(', ')}${assetIds.length > 5 ? '...' : ''}`);
    
    this.ws.send(JSON.stringify(subscription));
    assetIds.forEach(id => this.subscribedAssets.add(id));
  }

  /**
   * Subscribe to market updates for specific assets
   * ใช้ batching เพื่อลดการส่ง request รัวๆ
   */
  subscribeToAssets(assetIds: string[]): void {
    // Validate token IDs
    const validIds = assetIds.filter(id => {
      if (!id || typeof id !== 'string' || id.length < 10) {
        logger.warn(`Invalid token ID skipped: ${id}`);
        return false;
      }
      return true;
    });

    if (validIds.length === 0) {
      return;
    }

    // Add to pending subscriptions
    validIds.forEach(id => this.pendingSubscriptions.add(id));

    // If not connected, just queue them
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      logger.debug(`Queued ${validIds.length} subscriptions (WS not connected)`);
      return;
    }

    // Batch subscriptions to avoid rate limiting
    this.scheduleSubscriptionBatch();
  }

  /**
   * Schedule batched subscription send
   */
  private scheduleSubscriptionBatch(): void {
    if (this.subscriptionBatchTimeout) {
      return; // Already scheduled
    }

    this.subscriptionBatchTimeout = setTimeout(() => {
      this.subscriptionBatchTimeout = null;
      this.sendPendingSubscriptions();
    }, 500); // Wait 500ms to batch subscriptions
  }

  /**
   * Send pending subscriptions in batch
   */
  private sendPendingSubscriptions(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const newAssets = Array.from(this.pendingSubscriptions).filter(
      id => !this.subscribedAssets.has(id)
    );

    if (newAssets.length === 0) {
      this.pendingSubscriptions.clear();
      return;
    }

    // Send subscribe operation
    const subscription: WSSubscribeOperation = {
      assets_ids: newAssets,
      operation: 'subscribe',
    };

    logger.info(`📤 Subscribing to ${newAssets.length} new assets`);
    this.ws.send(JSON.stringify(subscription));
    
    newAssets.forEach(id => this.subscribedAssets.add(id));
    this.pendingSubscriptions.clear();
  }

  /**
   * Unsubscribe from market updates
   */
  unsubscribeFromAssets(assetIds: string[]): void {
    // Remove from pending and subscribed
    assetIds.forEach(id => {
      this.pendingSubscriptions.delete(id);
      this.subscribedAssets.delete(id);
    });

    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const subscription: WSSubscribeOperation = {
      assets_ids: assetIds,
      operation: 'unsubscribe',
    };

    this.ws.send(JSON.stringify(subscription));
    logger.debug(`Unsubscribed from ${assetIds.length} assets`);
  }

  /**
   * Clear subscription batch timeout
   */
  private clearSubscriptionBatch(): void {
    if (this.subscriptionBatchTimeout) {
      clearTimeout(this.subscriptionBatchTimeout);
      this.subscriptionBatchTimeout = null;
    }
  }

  /**
   * ตรวจสอบสถานะการเชื่อมต่อ
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * รับสถานะการเชื่อมต่อสำหรับ UI
   */
  getStatusInfo(): WSStatusInfo {
    return {
      status: this.connectionStatus,
      message: this.statusMessage,
      messagesReceived: this.messagesReceived,
      lastMessageTime: this.lastMessageTime,
      reconnectAttempts: this.reconnectAttempts,
      subscribedAssets: this.subscribedAssets.size,
    };
  }

  /**
   * อัพเดทสถานะการเชื่อมต่อ
   */
  private updateStatus(status: WSConnectionStatus, message: string): void {
    this.connectionStatus = status;
    this.statusMessage = message;
    this.emit('status_change', this.getStatusInfo());
  }

  /**
   * จัดการ message ที่ได้รับ
   */
  private handleMessage(message: RawWSMessage): void {
    const eventType = message.event_type;
    
    if (eventType === 'book') {
      logger.debug(`📥 Book update: ${message.asset_id?.substring(0, 20)}...`);
      this.emit('book', message as unknown as WSBookMessage);
    } else if (eventType === 'price_change') {
      this.emit('price_change', message as unknown as WSPriceChangeMessage);
    } else if (eventType) {
      logger.debug(`Unknown WS event type: ${eventType}`);
    }
  }

  /**
   * พยายามเชื่อมต่อใหม่ with exponential backoff + jitter
   */
  private async attemptReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      logger.error('Max reconnect attempts reached, falling back to REST polling');
      this.updateStatus('degraded', 'Degraded mode: ใช้ REST polling แทน');
      this.emit('max_reconnect_reached');
      return;
    }

    this.reconnectAttempts++;
    this.updateStatus('reconnecting', `กำลังเชื่อมต่อใหม่ (ครั้งที่ ${this.reconnectAttempts})`);
    
    // Exponential backoff with jitter
    const baseDelay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    const jitter = Math.random() * 1000;
    const totalDelay = Math.min(baseDelay + jitter, 30000);

    logger.info(`พยายามเชื่อมต่อใหม่ครั้งที่ ${this.reconnectAttempts} ใน ${Math.round(totalDelay)}ms`);
    
    await this.sleep(totalDelay);
    
    if (!this.shouldReconnect) {
      return;
    }
    
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

  /**
   * เริ่ม stale check - ตรวจสอบว่าได้รับ message หรือไม่
   */
  private startStaleCheck(): void {
    this.stopStaleCheck();
    
    this.staleCheckInterval = setInterval(() => {
      if (this.lastMessageTime) {
        const timeSinceLastMessage = Date.now() - this.lastMessageTime;
        // ถ้าไม่ได้รับ message นานกว่า 2 นาที ถือว่า stale
        if (timeSinceLastMessage > 120000) {
          logger.warn('WebSocket connection appears stale, reconnecting...');
          this.ws?.close();
        }
      }
    }, 60000); // ตรวจสอบทุก 1 นาที
  }

  /**
   * หยุด stale check
   */
  private stopStaleCheck(): void {
    if (this.staleCheckInterval) {
      clearInterval(this.staleCheckInterval);
      this.staleCheckInterval = null;
    }
  }

  /**
   * Test WebSocket connection - สำหรับปุ่มทดสอบใน Settings
   */
  async testConnection(testTokenIds: string[]): Promise<{
    success: boolean;
    message: string;
    messagesReceived: number;
    latencyMs: number;
  }> {
    const startTime = Date.now();
    let testMessagesReceived = 0;

    return new Promise((resolve) => {
      const testTimeout = setTimeout(() => {
        cleanup();
        resolve({
          success: testMessagesReceived > 0,
          message: testMessagesReceived > 0 
            ? `รับ ${testMessagesReceived} messages` 
            : 'ไม่ได้รับ message ใดๆ (อาจไม่มี activity)',
          messagesReceived: testMessagesReceived,
          latencyMs: Date.now() - startTime,
        });
      }, 10000); // Wait 10 seconds for test

      const onMessage = () => {
        testMessagesReceived++;
      };

      const cleanup = () => {
        clearTimeout(testTimeout);
        this.removeListener('book', onMessage);
        this.removeListener('price_change', onMessage);
      };

      this.on('book', onMessage);
      this.on('price_change', onMessage);

      // Subscribe to test tokens
      if (this.isConnected()) {
        this.subscribeToAssets(testTokenIds);
      } else {
        cleanup();
        resolve({
          success: false,
          message: 'WebSocket ไม่ได้เชื่อมต่อ',
          messagesReceived: 0,
          latencyMs: Date.now() - startTime,
        });
      }
    });
  }

  /**
   * Reset statistics
   */
  resetStats(): void {
    this.messagesReceived = 0;
    this.lastMessageTime = null;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export const wsClient = new WebSocketClient();
export default wsClient;
