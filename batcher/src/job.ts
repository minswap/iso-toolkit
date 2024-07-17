import { setTimeout } from "timers/promises";

import { onShutdown } from "./graceful-shutdown";
import logger from "./logger";
import { Duration } from ".";

export type RunRecurringJobParams = {
  name: string;
  interval: Duration;
  // need mainRedis if want to monitor job statuses
  job: () => Promise<void>;
};

// run job with consideration of job taking longer than interval
// if job finish less than interval, wait (interval - execution time) until next run
// if job finish longer than interval, start immediately
export async function runRecurringJob({
  name,
  job,
  interval,
}: RunRecurringJobParams): Promise<void> {
  const abortController = new AbortController();
  let shuttingDown = false;
  onShutdown(() => {
    shuttingDown = true;
    abortController.abort("shutdown");
  });

  while (true) {
    if (shuttingDown) {
      // break infinity loop when receive shutdown signal
      return;
    }

    const startTime = new Date();
    try {
      await job();
    } catch (err) {
      logger.error({ job: name, shuttingDown, signal: abortController.signal });
      logger.error(err);
    }

    const timeTook = Duration.between(startTime, new Date());
    logger.info(`done job ${name}`, { job_name: name, duration: timeTook });

    if (timeTook.lessThan(interval)) {
      try {
        await setTimeout(interval.milliseconds - timeTook.milliseconds, null, {
          signal: abortController.signal,
        });
      } catch (err) {
        // break sleep if receive shutdown signal
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
      }
    }
  }
}
