import logger from "./logger";

export type GracefulShutdownHandler = () => void;

const handlers: GracefulShutdownHandler[] = [];
let lock = false;

export function onShutdown(f: GracefulShutdownHandler): void {
  handlers.push(f);
}

function signalHandler(signal: string): void {
  // Some services (api,...) will call the signal handler more than once, so we need a lock to make sure to only run the handler once
  if (lock) {
    return;
  } else {
    lock = true;
  }

  logger.warn(`${signal} received, graceful shutdown...`);
  for (const handler of handlers) {
    handler();
  }
}

// call this function to turn graceful shutdown on
// use this to selectively enable graceful shutdown on some services, if it's stable then we can turn graceful shutdown on globally
export function useGracefulShutdown(): void {
  process.on("SIGINT", signalHandler);
  process.on("SIGTERM", signalHandler);
  process.on("SIGQUIT", signalHandler);

  process.on("uncaughtException", (error, origin) => {
    signalHandler("uncaughtException");
    logger.error("uncaughtException", { origin, error });
    process.exit(1);
  });

  process.on("unhandledRejection", (reason, promise) => {
    signalHandler("unhandledRejection");
    logger.error("unhandledRejection", { promise, reason });
    process.exit(1);
  });
}
