// =====================================================
// PolyArb Signal - Logger
// Structured logging with pino
// =====================================================

import pino from 'pino';
import { app } from 'electron';
import path from 'path';
import fs from 'fs';

// Get log directory
const getLogDir = (): string => {
  try {
    const userDataPath = app.getPath('userData');
    const logDir = path.join(userDataPath, 'logs');
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    return logDir;
  } catch {
    // Fallback for when app is not ready
    return process.cwd();
  }
};

// Create logger
export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    targets: [
      // Console output
      {
        target: 'pino-pretty',
        level: 'info',
        options: {
          colorize: true,
          translateTime: 'SYS:standard',
          ignore: 'pid,hostname',
        },
      },
    ],
  },
});

// Export default
export default logger;
