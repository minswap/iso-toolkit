import * as T from "@minswap/translucent";
import logger from "./logger";
import { checkSkipGenReward, getEnv } from "./utils";
import { runRecurringJob } from "./job";
import { Duration } from "./duration";
import JSONBig from "json-bigint";
import type Redis from "ioredis";
import { newRedis } from "./redis";

const BATCH_SIZE = 40;
const REDIS_KEY = "reward_utxos";

type RunGenRewardsOptions = {
  t: T.Translucent;
  redis: Redis;
  batcherAddress: T.Address;
  rewardUnit: T.Unit;
};

async function runGenRewards(options: RunGenRewardsOptions): Promise<void> {
  const { t, redis, batcherAddress, rewardUnit } = options;
  const C = T.CModuleLoader.get;

  // Check Skip
  let finalRewardData = await redis.get("final_reward");
  if (!finalRewardData) {
    logger.warn("SKIP | Not Final Reward");
    return;
  }

  // Check all seeds have been seeded or not?
  const skipGenReward = await checkSkipGenReward(redis);
  if (skipGenReward) {
    logger.info("SKIP | Gen all seeds done!");
    return;
  }

  // parse Redis Data
  const mapReward = JSONBig.parse(finalRewardData);

  // get all users's stake address
  const userStakeAddresses = Object.keys(mapReward);

  let sliceIndex = 0;
  // Chunk into batch
  while (sliceIndex < userStakeAddresses.length) {
    const batchStakeAddresses = userStakeAddresses.slice(
      sliceIndex,
      sliceIndex + BATCH_SIZE,
    );
    sliceIndex += BATCH_SIZE;

    // init Tx Builder
    const txBuilder = t.newTx();

    // Mapping stake-address -> seed-transaction's output index
    const mapOutputIndex: Record<string, number> = {};
    let outputIndex = 0;

    for (const stakeAddress of batchStakeAddresses) {
      // SKIP if already seed this user
      const rewardExist = await redis.hget(REDIS_KEY, stakeAddress);
      if (rewardExist) {
        logger.info(`SKIP|reward-exist|stake_address=${stakeAddress}`);
        continue;
      }

      /**
       * prepare datum
       * Datum <=> StakeAddress
       */
      const saHex = T.fromText(stakeAddress);
      const saBytes = T.fromHex(saHex);
      const plutusData = C.PlutusData.new_bytes(saBytes);
      const plutusDataRaw = T.toHex(plutusData.to_bytes());
      plutusData.free();

      // prepare assets, include reward tokens
      const assets: T.Assets = {
        lovelace: 1_500_000n,
      };
      if (mapReward[stakeAddress] && mapReward[stakeAddress] > 0n) {
        assets[rewardUnit] = mapReward[stakeAddress];
      }

      // pay seed for user
      txBuilder.payToAddressWithData(
        batcherAddress,
        { inline: plutusDataRaw },
        assets,
      );

      // update Mapping
      mapOutputIndex[stakeAddress] = outputIndex;
      outputIndex++;
    }

    // check if Tx gen any new reward utxo
    if (Object.keys(mapOutputIndex).length > 0) {
      // build -> sign -> finalize Tx
      // trick Translucent
      const completeTx = await txBuilder.complete();
      const signedTx = await completeTx.sign().complete();
      const txHash = await signedTx.submit();

      // Insert to Redis
      for (const [key, outputIndex] of Object.entries(mapOutputIndex)) {
        const outRef: T.OutRef = {
          txHash,
          outputIndex,
        };
        await redis.hset(REDIS_KEY, key, JSON.stringify(outRef));
      }

      await t.awaitTx(txHash, 5000);
      logger.info(`gen-seed|txHash=${txHash}`);
    }
  }
}

const main = async () => {
  logger.info("Start | Gen user rewards UTxOs");
  await T.loadModule();
  await T.CModuleLoader.load();

  const network: T.MaestroSupportedNetworks = getEnv(
    "NETWORK",
  ) as T.MaestroSupportedNetworks;
  const maestroApiKey = getEnv("MAESTRO_API_KEY");
  const fundSeedPhase = getEnv("FUND_SEED_PHASE");
  const redisUrl = getEnv("REDIS_URL");
  const batcherAddress = getEnv("BATCHER_ADDRESS");
  const rewardUnit = getEnv("REWARD_UNIT");

  const redis = newRedis(redisUrl, "batcher");
  const maestro = new T.Maestro({ network, apiKey: maestroApiKey });
  const t = await T.Translucent.new(maestro, network);
  t.selectWalletFromSeed(fundSeedPhase);

  await runRecurringJob({
    name: "fiso-gen-rewards",
    interval: Duration.newSeconds(30),
    job: async () => {
      await runGenRewards({ t, redis, batcherAddress, rewardUnit });
    },
  });
};

main();
