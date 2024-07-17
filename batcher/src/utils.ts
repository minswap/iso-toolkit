import logger from "./logger";
import JSONBig from "json-bigint";
import type { RedisReadOnly } from "./redis";

export function getEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    logger.error(`Require environment variable ${key}`);
    throw new Error("Server init error");
  }
  return val;
}

export async function checkSkipGenReward(
  redis: RedisReadOnly,
): Promise<boolean> {
  // get all final reward
  const finalReward = await redis.get("final_reward");

  // don't skip if final reward is None
  if (!finalReward) {
    return false;
  }

  // parse JSON
  const data = JSONBig.parse(finalReward);
  // get how many total rewards
  const finalRewardLength = Object.keys(data).length;

  // get how many reward utxos have been seeded.
  const rewardLen = await redis.hlen("reward_utxos");

  // SKIP if all rewards have been seeded.
  return rewardLen === finalRewardLength;
}
