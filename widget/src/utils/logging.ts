// src/utils/logger.ts

export const LogLevel = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  NONE: 4,
} as const;

export type LogLevel = (typeof LogLevel)[keyof typeof LogLevel];

export interface LoggerConfig {
  level: LogLevel;
  prefix?: string;
  timestamp?: boolean;
  colors?: boolean;
}

/**
 * A singleton logger class that provides structured logging functionality with configurable options.
 *
 * @remarks
 * This logger is designed to work in browser environments and provides:
 * - Singleton pattern for consistent logging across the application
 * - Configurable log levels, colors, timestamps, and prefixes
 * - Console-based output with styled formatting
 * - Performance timing utilities
 * - Log grouping capabilities
 *
 * @example
 * ```typescript
 * // Get the singleton instance
 * const logger = Logger.getInstance();
 *
 * // Configure the logger
 * Logger.setConfig({
 *   level: LogLevel.DEBUG,
 *   prefix: "[MyApp]",
 *   colors: true,
 *   timestamp: true
 * });
 *
 * // Use logging methods
 * logger.info("Application started");
 * logger.warn("This is a warning");
 * logger.error("An error occurred", error);
 *
 * // Performance timing
 * logger.time("operation");
 * // ... some operation
 * logger.timeEnd("operation");
 *
 * // Log grouping
 * logger.group("User Actions");
 * logger.info("User clicked button");
 * logger.info("User filled form");
 * logger.groupEnd();
 * ```
 */
export class Logger {
  private config: LoggerConfig;
  private static instance: Logger;

  constructor(config: Partial<LoggerConfig> = {}) {
    const isDevelopment = process.env.NODE_ENV === "development";

    this.config = {
      level: isDevelopment ? LogLevel.INFO : LogLevel.WARN,
      prefix: "[Eylo]",
      timestamp: true,
      colors: true,
      ...config,
    };
  }

  static getInstance(config: Partial<LoggerConfig> = {}): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger(config);
    }
    return Logger.instance;
  }

  static setConfig(config: Partial<LoggerConfig>): void {
    const instance = Logger.getInstance();
    instance.config = { ...instance.config, ...config };
  }

  private format(level: string, ...args: any[]): any[] {
    const parts: any[] = [];

    if (this.config.colors && typeof console !== "undefined") {
      const colors: Record<string, string> = {
        DEBUG: "color: #888",
        INFO: "color: #2196F3",
        WARN: "color: #FF9800",
        ERROR: "color: #F44336",
      };
      parts.push(`%c${this.config.prefix} ${level}`, colors[level] || "");
    } else {
      parts.push(`${this.config.prefix} ${level}`);
    }

    if (this.config.timestamp) {
      parts[0] += ` [${new Date().toISOString()}]`;
    }

    return [...parts, ...args];
  }

  debug(...args: any[]): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.log(...this.format("DEBUG", ...args));
    }
  }

  info(...args: any[]): void {
    if (this.config.level <= LogLevel.INFO) {
      console.log(...this.format("INFO", ...args));
    }
  }

  warn(...args: any[]): void {
    if (this.config.level <= LogLevel.WARN) {
      console.warn(...this.format("WARN", ...args));
    }
  }

  error(...args: any[]): void {
    if (this.config.level <= LogLevel.ERROR) {
      console.error(...this.format("ERROR", ...args));
    }
  }

  group(label: string): void {
    if (this.config.level < LogLevel.NONE) {
      console.group(`${this.config.prefix} ${label}`);
    }
  }

  groupEnd(): void {
    if (this.config.level < LogLevel.NONE) {
      console.groupEnd();
    }
  }

  time(label: string): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.time(`${this.config.prefix} ${label}`);
    }
  }

  timeEnd(label: string): void {
    if (this.config.level <= LogLevel.DEBUG) {
      console.timeEnd(`${this.config.prefix} ${label}`);
    }
  }
}

// Export a default logger instance
export const logger = Logger.getInstance();
