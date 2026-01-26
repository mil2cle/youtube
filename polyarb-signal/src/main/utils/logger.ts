// =====================================================
// PolyArb Signal - Logger Utility
// จัดการ logging สำหรับ main process
// =====================================================

import { app } from 'electron';
import fs from 'fs';
import path from 'path';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: unknown;
}

class Logger {
  private logDir: string = '';
  private logFile: string = '';
  private maxFileSize = 5 * 1024 * 1024; // 5MB
  private maxFiles = 5;
  private initialized = false;

  private ensureInit(): void {
    if (this.initialized) return;
    try {
      this.logDir = path.join(app.getPath('userData'), 'logs');
      this.logFile = path.join(this.logDir, 'app.log');
      if (!fs.existsSync(this.logDir)) {
        fs.mkdirSync(this.logDir, { recursive: true });
      }
      this.initialized = true;
    } catch {
      // App not ready yet, use fallback
      this.logDir = process.cwd();
      this.logFile = path.join(this.logDir, 'app.log');
    }
  }

  private formatMessage(level: LogLevel, message: string, data?: unknown): string {
    const timestamp = new Date().toISOString();
    const entry: LogEntry = { timestamp, level, message };
    if (data !== undefined) {
      entry.data = data;
    }
    return JSON.stringify(entry);
  }

  private rotateIfNeeded(): void {
    try {
      if (!fs.existsSync(this.logFile)) return;
      
      const stats = fs.statSync(this.logFile);
      if (stats.size < this.maxFileSize) return;

      for (let i = this.maxFiles - 1; i >= 1; i--) {
        const oldFile = `${this.logFile}.${i}`;
        const newFile = `${this.logFile}.${i + 1}`;
        if (fs.existsSync(oldFile)) {
          if (i === this.maxFiles - 1) {
            fs.unlinkSync(oldFile);
          } else {
            fs.renameSync(oldFile, newFile);
          }
        }
      }
      fs.renameSync(this.logFile, `${this.logFile}.1`);
    } catch {
      // Ignore rotation errors
    }
  }

  private write(level: LogLevel, message: string, data?: unknown): void {
    this.ensureInit();
    const formattedMessage = this.formatMessage(level, message, data);
    
    // Console output
    const consoleMethod = level === 'error' ? console.error : 
                          level === 'warn' ? console.warn : 
                          level === 'debug' ? console.debug : console.log;
    consoleMethod(`[${level.toUpperCase()}] ${message}`, data !== undefined ? data : '');

    // File output
    try {
      this.rotateIfNeeded();
      fs.appendFileSync(this.logFile, formattedMessage + '\n');
    } catch {
      // Ignore file write errors
    }
  }

  debug(message: string, data?: unknown): void {
    this.write('debug', message, data);
  }

  info(message: string, data?: unknown): void {
    this.write('info', message, data);
  }

  warn(message: string, data?: unknown): void {
    this.write('warn', message, data);
  }

  error(message: string, data?: unknown): void {
    this.write('error', message, data);
  }

  getRecentLogs(lines = 100): LogEntry[] {
    this.ensureInit();
    try {
      if (!fs.existsSync(this.logFile)) return [];
      
      const content = fs.readFileSync(this.logFile, 'utf-8');
      const allLines = content.trim().split('\n').filter(Boolean);
      const recentLines = allLines.slice(-lines);
      
      return recentLines.map(line => {
        try {
          return JSON.parse(line) as LogEntry;
        } catch {
          return { timestamp: '', level: 'info' as LogLevel, message: line };
        }
      });
    } catch {
      return [];
    }
  }

  clearLogs(): void {
    this.ensureInit();
    try {
      if (fs.existsSync(this.logFile)) {
        fs.writeFileSync(this.logFile, '');
      }
      for (let i = 1; i <= this.maxFiles; i++) {
        const rotatedFile = `${this.logFile}.${i}`;
        if (fs.existsSync(rotatedFile)) {
          fs.unlinkSync(rotatedFile);
        }
      }
    } catch {
      // Ignore clear errors
    }
  }

  getLogDir(): string {
    this.ensureInit();
    return this.logDir;
  }
}

export const logger = new Logger();
export default logger;
