// src/utils/logger.ts

import { Logger, LogLevel } from "@eylo/utils";

const logger = Logger.getInstance({
  prefix: "[Eylo Widget]",
  timestamp: true,
  colors: true,
  level: process.env.NODE_ENV === "development" ? LogLevel.DEBUG : LogLevel.WARN,
});

export { logger, Logger };
