// =====================================================
// PolyArb Signal - Auto Launch Utility
// จัดการ Windows startup registration
// =====================================================

import { app } from 'electron';
import path from 'path';
import { logger } from './logger';

// Windows Registry paths
const REGISTRY_KEY = 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run';
const APP_NAME = 'PolyArb Signal';

class AutoLaunch {
  private isEnabled = false;

  /**
   * ตรวจสอบว่าเปิดใช้งาน auto-launch หรือไม่
   */
  async isAutoLaunchEnabled(): Promise<boolean> {
    if (process.platform !== 'win32') {
      return false;
    }

    try {
      const { execSync } = await import('child_process');
      const result = execSync(`reg query "${REGISTRY_KEY}" /v "${APP_NAME}"`, {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return result.includes(APP_NAME);
    } catch {
      return false;
    }
  }

  /**
   * เปิดใช้งาน auto-launch
   */
  async enable(): Promise<boolean> {
    if (process.platform !== 'win32') {
      logger.warn('Auto-launch is only supported on Windows');
      return false;
    }

    try {
      const exePath = app.getPath('exe');
      const { execSync } = await import('child_process');
      
      // Add to Windows startup registry
      execSync(
        `reg add "${REGISTRY_KEY}" /v "${APP_NAME}" /t REG_SZ /d "\\"${exePath}\\"" /f`,
        { stdio: ['pipe', 'pipe', 'pipe'] }
      );

      this.isEnabled = true;
      logger.info('Auto-launch enabled');
      return true;
    } catch (error) {
      logger.error('Failed to enable auto-launch:', error);
      return false;
    }
  }

  /**
   * ปิดใช้งาน auto-launch
   */
  async disable(): Promise<boolean> {
    if (process.platform !== 'win32') {
      return false;
    }

    try {
      const { execSync } = await import('child_process');
      
      // Remove from Windows startup registry
      execSync(
        `reg delete "${REGISTRY_KEY}" /v "${APP_NAME}" /f`,
        { stdio: ['pipe', 'pipe', 'pipe'] }
      );

      this.isEnabled = false;
      logger.info('Auto-launch disabled');
      return true;
    } catch (error) {
      // Key might not exist, which is fine
      logger.debug('Auto-launch was not enabled');
      return true;
    }
  }

  /**
   * สลับสถานะ auto-launch
   */
  async toggle(): Promise<boolean> {
    const enabled = await this.isAutoLaunchEnabled();
    if (enabled) {
      return this.disable();
    } else {
      return this.enable();
    }
  }
}

export const autoLaunch = new AutoLaunch();
export default autoLaunch;
