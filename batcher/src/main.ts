import * as T from "@minswap/translucent";
import { Client } from "pg";
import logger from "./logger";
import { checkSkipGenReward, getEnv } from "./utils";
import { runRecurringJob } from "./job";
import { Duration } from "./duration";
import { newRedisReadonly, type RedisReadOnly } from "./redis";
import JSONBig from "json-bigint";

const BATCH_SIZE = 30;

type RunBatcherOptions = {
  t: T.Translucent;
  redis: RedisReadOnly;
  dbClient: Client;
  rewardUnit: T.Unit;
  fundAddress: T.Address;
};

function parseStakeAddress(utxo: T.UTxO): string | undefined {
  const C = T.CModuleLoader.get;
  try {
    // parse Inline Datum Hex => C PlutusData
    const plutusData = C.PlutusData.from_bytes(T.fromHex(utxo.datum!));

    // convert it => utf8 string
    return Buffer.from(plutusData.as_bytes()!).toString("utf-8");
  } catch {
    return undefined;
  }
}

async function runBatcher(options: RunBatcherOptions): Promise<void> {
  const { t, redis, dbClient, rewardUnit, fundAddress } = options;

  // Check Skip
  let finalRewardData = await redis.get("final_reward");
  if (!finalRewardData) {
    logger.warn("SKIP | Not Final Reward");
    return;
  }

  // Check all seeds have been seeded or not?
  const skipGenReward = await checkSkipGenReward(redis);
  if (!skipGenReward) {
    // should wait until seeding finish!
    logger.warn("SKIP | Seeding not finished yet!");
    return;
  }

  // Get Batcher UTxOs
  const batcherUtxos = await t.wallet.getUtxos();

  // We only handle BATCH_SIZE Order per batch
  let userUtxos = batcherUtxos
    .filter((u) => u.assets["lovelace"] === 2_000_000n)
    .slice(0, BATCH_SIZE);
  if (!userUtxos.length) {
    logger.warn("SKIP | No Order");
    return;
  }

  // mapping between stake-address -> Reward UTxO
  const mapRewardUtxo: Record<string, T.UTxO> = {};
  for (const u of batcherUtxos) {
    // Seed UTxO contains reward Tokens
    if (u.assets[rewardUnit] && u.assets[rewardUnit] > 0n) {
      const sa = parseStakeAddress(u);
      if (sa) {
        mapRewardUtxo[sa] = u;
      }
    }
  }

  // Init TxBuilder
  const txBuilder = t.newTx();

  // init Input To Chosoe
  const inputsToChoose: T.UTxO[] = [];

  // loop userUTxOs to build Tx
  for (const userUtxo of userUtxos) {
    // Should try-catch to prevent crash batching
    try {
      // This Query aims to get User Stake Address, Address from Order's UTxO
      const rawQuery = `
      select stake_address.view, tx_out.address
      from
        tx inner join tx_in on tx.id = tx_in.tx_in_id
        inner join tx_out on tx_in.tx_out_id = tx_out.tx_id and tx_in.tx_out_index = tx_out.index
        inner join stake_address on stake_address.id = tx_out.stake_address_id
      where
        tx.hash='\\x${userUtxo.txHash}';
    `;
      const data = await dbClient.query(rawQuery);
      const stakeAddress = data.rows[0].view;
      const userAddress = data.rows[0].address;

      // get reward UTxO, skip if not found
      const rewardUtxo = mapRewardUtxo[stakeAddress];
      if (!rewardUtxo) {
        logger.warn(
          `SKIP|already_redeem OR no_reward|stake_address=${stakeAddress}`,
        );
        continue;
      }

      // prepare user values
      const userRewardAssets = {
        ...rewardUtxo.assets,
        lovelace: 1_500_000n,
      };

      logger.info(
        `redeem to user|${JSONBig.stringify(
          {
            rewardInput: {
              txHash: rewardUtxo.txHash,
              index: rewardUtxo.outputIndex,
            },
            userInput: { txHash: userUtxo.txHash, index: userUtxo.outputIndex },
            userAddress,
            userRewardAssets,
          },
          null,
          2,
        )}`,
      );

      // collect Order, Reward UTxO -> pays to User
      txBuilder
        .collectFrom([rewardUtxo, userUtxo])
        .payToAddress(userAddress, userRewardAssets);

      // only choose inputs that required
      inputsToChoose.push(rewardUtxo, userUtxo);
    } catch (err) {
      logger.error("handle order failed");
      logger.error(err);
    }
  }

  // Check we redeem any
  if (inputsToChoose.length > 0) {
    // Build -> Sign -> Finalize
    // Should return Change Fund to Fund Address
    const completeTx = await txBuilder.complete({
      inputsToChoose,
      change: { address: fundAddress },
    });
    const signedTx = await completeTx.sign().complete();

    // submit tx
    const txHash = await signedTx.submit();
    logger.info(`Batch Success|txHash=${txHash}`);

    // wait Tx tobe confirmed! before run next batch
    await t.awaitTx(txHash, 5000);
  } else {
    logger.info("SKIP | no redeem");
  }
}

const main = async () => {
  logger.info("Start | Batcher redeem rewards");
  // load modules
  await T.loadModule();
  await T.CModuleLoader.load();

  // Get needed things
  const network: T.MaestroSupportedNetworks = getEnv(
    "NETWORK",
  ) as T.MaestroSupportedNetworks;
  const maestroApiKey = getEnv("MAESTRO_API_KEY");
  const batcherSeedPhase = getEnv("BATCHER_SEED_PHASE");
  const redisUrl = getEnv("REDIS_URL");
  const dbConfig = {
    user: getEnv("DB_USER"),
    host: getEnv("DB_HOST"),
    database: getEnv("DB_NAME"),
    password: getEnv("DB_PASSWORD"),
    port: Number(getEnv("DB_PORT")),
  };
  const rewardUnit = getEnv("REWARD_UNIT");
  const fundAddress = getEnv("FUND_ADDRESS");

  // Init connections
  const redis = newRedisReadonly(redisUrl, "batcher");
  const dbClient = new Client(dbConfig);
  const maestro = new T.Maestro({ network, apiKey: maestroApiKey });
  const t = await T.Translucent.new(maestro, network);
  t.selectWalletFromSeed(batcherSeedPhase);
  await dbClient.connect();

  // run rucurring as Cronjob
  await runRecurringJob({
    name: "fiso-batcher",
    interval: Duration.newSeconds(30),
    job: async () => {
      await runBatcher({ t, redis, dbClient, rewardUnit, fundAddress });
    },
  });
};

main();
