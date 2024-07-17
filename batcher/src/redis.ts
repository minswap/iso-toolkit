import { Redis, type RedisOptions } from "ioredis";
import { onShutdown } from "./graceful-shutdown";

export function newRedis(
  url: string,
  connectionName: string,
  options?: RedisOptions,
): Redis {
  const redis = new Redis(url, {
    ...options,
    db: 0,
    connectionName,
    enableReadyCheck: true,
    maxRetriesPerRequest: 1,
    showFriendlyErrorStack: false,
    retryStrategy(times): number {
      return Math.min(times * 10, 2000);
    },
  });
  // QUIT is deprecated, it's recommended to close connection immediately
  // Read more: https://redis.io/commands/quit/
  onShutdown(() => redis.disconnect());
  return redis;
}

export type RedisReadOnly = Pick<
  Redis,
  | "get"
  | "mget"
  | "hget"
  | "hmget"
  | "hgetall"
  | "hlen"
  | "hkeys"
  | "hvals"
  | "lrange"
  | "smismember"
  | "disconnect"
  | "quit"
>;

export function newRedisReadonly(
  url: string,
  connectionName: string,
  options?: RedisOptions,
): RedisReadOnly {
  return newRedis(url, connectionName, {
    ...options,
    readOnly: true,
  });
}
