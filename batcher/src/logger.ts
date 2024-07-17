import { createLogger, format, transports } from "winston";

const { combine, timestamp, printf, colorize, align } = format;

const logger = createLogger({
  level: "info",
  format: combine(
    colorize({ all: true }),
    timestamp({
      format: "YYYY-MM-DD hh:mm:ss.SSS A",
    }),
    align(),
    format.json(),
    printf(
      ({ timestamp, level, message }) => `[${timestamp}] ${level}: ${message}`,
    ),
  ),
  transports: [new transports.Console()],
});

export default logger;
