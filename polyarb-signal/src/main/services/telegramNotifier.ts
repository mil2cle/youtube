// =====================================================
// PolyArb Signal - Telegram Notifier
// ส่งแจ้งเตือนผ่าน Telegram Bot
// =====================================================

import { TELEGRAM } from '../../shared/constants';
import { ArbSignal, AppSettings } from '../../shared/types';
import { logger } from '../utils/logger';

class TelegramNotifier {
  private botToken: string = '';
  private chatId: string = '';
  private isConfigured = false;

  /**
   * ตั้งค่า credentials
   */
  configure(settings: AppSettings['telegram']): void {
    this.botToken = settings.botToken;
    this.chatId = settings.chatId;
    this.isConfigured = !!(this.botToken && this.chatId);
    
    if (this.isConfigured) {
      logger.info('Telegram notifier configured');
    } else {
      logger.warn('Telegram notifier not configured - missing token or chat ID');
    }
  }

  /**
   * ตรวจสอบว่าตั้งค่าแล้วหรือยัง
   */
  isReady(): boolean {
    return this.isConfigured;
  }

  /**
   * ส่งข้อความทดสอบ
   */
  async sendTestMessage(): Promise<{ success: boolean; error?: string }> {
    if (!this.isConfigured) {
      return { success: false, error: 'Telegram not configured' };
    }

    const message = `🧪 *PolyArb Signal Test*\n\nการทดสอบการเชื่อมต่อสำเร็จ!\nTimestamp: ${new Date().toISOString()}`;

    return this.sendMessage(message);
  }

  /**
   * ส่ง signal alert
   */
  async sendSignalAlert(signal: ArbSignal): Promise<{ success: boolean; error?: string }> {
    if (!this.isConfigured) {
      logger.warn('Cannot send signal - Telegram not configured');
      return { success: false, error: 'Telegram not configured' };
    }

    const emoji = signal.isLowDepth ? '⚠️' : '🎯';
    const depthWarning = signal.isLowDepth ? '\n⚠️ *LOW DEPTH WARNING*' : '';
    
    const message = `${emoji} *ARBITRAGE SIGNAL*${depthWarning}

📊 *Market:* ${this.escapeMarkdown(signal.marketQuestion)}

💰 *Prices:*
• YES Ask: ${(signal.yesAsk * 100).toFixed(1)}¢
• NO Ask: ${(signal.noAsk * 100).toFixed(1)}¢
• Sum: ${(signal.sumCost * 100).toFixed(1)}¢

📈 *Edge:* ${(signal.effectiveEdge * 100).toFixed(2)}%
🎯 *Threshold:* ${(signal.threshold * 100).toFixed(1)}%

📦 *Depth:*
• YES: $${signal.yesAskDepth.toFixed(0)}
• NO: $${signal.noAskDepth.toFixed(0)}

⏱️ *Latency:* ${signal.latencyMs}ms
🏷️ *Tier:* ${signal.tier}

🔗 [Open on Polymarket](${signal.polymarketUrl})`;

    return this.sendMessage(message);
  }

  /**
   * ส่งข้อความทั่วไป
   */
  async sendMessage(text: string): Promise<{ success: boolean; error?: string }> {
    if (!this.isConfigured) {
      return { success: false, error: 'Telegram not configured' };
    }

    try {
      const url = `${TELEGRAM.API_BASE}${this.botToken}/sendMessage`;
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_id: this.chatId,
          text: text.slice(0, TELEGRAM.MAX_MESSAGE_LENGTH),
          parse_mode: 'Markdown',
          disable_web_page_preview: false,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        const errorMsg = data.description || 'Unknown error';
        logger.error('Telegram API error:', errorMsg);
        return { success: false, error: errorMsg };
      }

      logger.debug('Telegram message sent successfully');
      return { success: true };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      logger.error('Failed to send Telegram message:', errorMsg);
      return { success: false, error: errorMsg };
    }
  }

  /**
   * Escape special characters for Markdown
   */
  private escapeMarkdown(text: string): string {
    return text
      .replace(/\*/g, '\\*')
      .replace(/_/g, '\\_')
      .replace(/\[/g, '\\[')
      .replace(/\]/g, '\\]')
      .replace(/`/g, '\\`');
  }
}

export const telegramNotifier = new TelegramNotifier();
export default telegramNotifier;
