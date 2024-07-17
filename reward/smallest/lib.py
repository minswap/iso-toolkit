import csv
import json
import logging
from collections import OrderedDict, namedtuple
from decimal import Decimal
from multiprocessing.pool import ThreadPool
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db import connection

from smallest.models import *
from smallest.utils import split_array_index, round_down

log = logging.getLogger('main')
redis = cache.client.get_client(True)

STAKE_QUERY = """
SELECT d1.addr_id
  FROM delegation d1,
       pool_hash
  WHERE pool_hash.id = d1.pool_hash_id
    AND pool_hash.id = {pool_id}
    AND d1.tx_id <= {max_tx}
    AND NOT EXISTS
      (SELECT TRUE
      FROM delegation d2
      WHERE d2.addr_id = d1.addr_id
    AND d2.tx_id
      > d1.tx_id
    AND d2.tx_id <= {max_tx})
    AND NOT EXISTS
      (SELECT TRUE
      FROM stake_deregistration
      WHERE stake_deregistration.addr_id = d1.addr_id
    AND stake_deregistration.tx_id
      > d1.tx_id
    AND stake_deregistration.tx_id <= {max_tx})
"""

TOTAL_STAKE_QUERY = """
SELECT sum(total)
FROM (with const as (select to_timestamp('{last_block}', 'YYYY-MM-DD HH24:MI:SS') as effective_time_)
      select sum(t.value) total
      from const
               cross join tx_out as t
               inner join tx as generating_tx on generating_tx.id = t.tx_id
               inner join block as generating_block on generating_block.id = generating_tx.block_id
               left join tx_in as consuming_input on consuming_input.tx_out_id = generating_tx.id
          and consuming_input.tx_out_index = t.index
               left join tx as consuming_tx on consuming_tx.id = consuming_input.tx_in_id
               left join block as consuming_block on consuming_block.id = consuming_tx.block_id
      WHERE
        t.stake_address_id IN ({stake_addr_ids})
        AND ( -- Ommit outputs from genesis after Allegra hard fork
              const.effective_time_ < '2020-12-16 21:44:00'
              or generating_block.epoch_no is not null
          )
        AND const.effective_time_ >= generating_block.time -- Only outputs from blocks generated in the past
        AND ( -- Only outputs consumed in the future or unconsumed outputs
              const.effective_time_ <= consuming_block.time or consuming_input.id IS NULL
          )
      UNION
      SELECT sum(amount)
      FROM reward
      WHERE 
        reward.addr_id IN ({stake_addr_ids})
        AND reward.spendable_epoch <= {epoch}
      UNION
      SELECT sum(amount)
      FROM reserve
      WHERE 
        reserve.addr_id IN ({stake_addr_ids}) 
        AND reserve.tx_id <= {max_tx}
      UNION
      SELECT SUM(amount)
      FROM treasury
      WHERE 
        treasury.addr_id IN ({stake_addr_ids})
        AND treasury.tx_id <= {max_tx}
      UNION
      SELECT -sum(amount)
      FROM withdrawal
      WHERE
        withdrawal.addr_id IN ({stake_addr_ids})
        AND withdrawal.tx_id <= {max_tx}
     ) AS t;
"""

"""
The GEN_SEED_QUERY is designed to retrieve specific delegation events and their associated block details.
The query focuses on the initial delegation transactions for specific pools \
and ensures that only the latest delegation events up to a given epoch are considered.
Parameters
- {pool_ids}: A list of pool hash IDs.
- {start_epoch}: Start of ISO.
- {end_epoch}: End of ISO.
Notes:
- Retrieve the latest delegation events up to a certain epoch for a specific set of pools.
- Ensure that only the most recent delegation for each address is considered, \
    avoiding any duplicate or outdated delegation records.
- Active epoch = Epoch + 2 cause delegation need 2 epochs to be activate.
"""
GEN_SEED_QUERY = """
SELECT d1.addr_id, d1.pool_hash_id, b.epoch_no, b.time, b.block_no
FROM delegation d1
         INNER JOIN tx t ON d1.tx_id = t.id
         INNER JOIN block b ON b.id = t.block_id
WHERE d1.pool_hash_id IN ({pool_ids})
  AND NOT EXISTS(
    SELECT TRUE FROM delegation d2 
    WHERE d2.active_epoch_no < {end_epoch} AND d2.addr_id = d1.addr_id AND d2.tx_id > d1.tx_id
  )
  AND d1.active_epoch_no >= {start_epoch} AND d1.active_epoch_no < {end_epoch};
"""


class IsoManager:
    delegation = None
    reward_per_epoch = None
    map_address = None
    pool_ids = None

    def __init__(self, pools, epoch_start, epoch_end, total_reward, smallest_bonus, whale_limiter):
        self.pools = pools
        self.epoch_start = epoch_start
        self.epoch_end = epoch_end
        self.total_reward = total_reward
        self.smallest_bonus = smallest_bonus
        self.whale_limiter = whale_limiter
        self.reward_per_epoch = Decimal(total_reward / (epoch_end - epoch_start))

    def build_rewards(self):
        seeds = self.gen_seeds()
        set_epoch_no = {*[s.get('epoch_no') for s in seeds]}
        for epoch in set_epoch_no:
            self.fetch_pools(epoch)

        for epoch in range(self.epoch_start, self.epoch_end):
            self.gen_epoch_reward(epoch)

        self.gen_final_reward()

    def get_pool_ids(self):
        if self.pool_ids:
            return self.pool_ids
        self.pool_ids = PoolHash.objects.filter(view__in=self.pools).pk_list()
        return self.pool_ids

    def get_delegation(self):
        if self.delegation:
            return self.delegation

        pool_ids = self.get_pool_ids()
        query = Delegation.objects.filter(pool_hash_id__in=pool_ids)

        # on each epoch, get last delegation of stake address
        m = {}
        for d in query:
            k = (d.addr_id, d.active_epoch_no)
            if k not in m:
                m[k] = (d.tx_id, d.pool_hash_id)
            else:
                tx_id, _ = m[k]
                if tx_id < d.tx_id:
                    m[k] = (d.tx_id, d.pool_hash_id)

        # get transaction info like: epoch, time, tx_id
        tx_ids = [d[0] for d in m.values()]
        map_tx_block_id = {}
        map_block_id_block = {}
        for start, end in split_array_index(len(tx_ids)):
            d = dict(Tx.objects.filter(id__in=tx_ids[start:end]).values_list('id', 'block_id'))
            map_tx_block_id.update(d)
            for b in Block.objects.filter(id__in=d.values()):
                map_block_id_block[b.id] = b

        result = []
        for k, v in m.items():
            addr_id, active_epoch_no = k
            tx_id, pool_hash_id = v
            b = map_block_id_block[map_tx_block_id[tx_id]]
            result.append({
                'addr_id': addr_id,
                'active_epoch_no': active_epoch_no,
                'tx_id': tx_id,
                'pool_hash_id': pool_hash_id,
                'epoch_no': b.epoch_no,
                'time': b.time.strftime('%Y-%m-%dT%H:%M:%S'),
            })
        result = sorted(result, key=lambda kk: (kk['active_epoch_no'], kk['pool_hash_id']))
        self.delegation = result
        return self.delegation

    def get_map_address(self):
        if self.map_address:
            return self.map_address
        delegation = self.get_delegation()
        addr_ids = [d['addr_id'] for d in delegation]
        self.map_address = dict(StakeAddress.objects.filter(id__in=addr_ids).values_list('id', 'view'))
        return self.map_address

    def get_point(self, lovelace, smallest):
        if self.whale_limiter:
            bound = Decimal(self.whale_limiter) * Decimal('1e6')  # Convert to Decimal
            point = lovelace if lovelace <= bound else bound + (lovelace - bound) ** Decimal('0.9')
        else:
            point = lovelace

        if smallest and self.smallest_bonus:
            point = point * Decimal(self.smallest_bonus + 100) / Decimal(100)

        return int(point)

    def gen_final_reward(self):
        log.info("generating_final_reward|START")

        user_rewards = defaultdict(Decimal)

        all_data = redis.hgetall('epoch_reward')

        if len(all_data.keys()) == self.epoch_end - self.epoch_start:
            log.info("generating_final_reward|SKIP|ALL_DONE")
            return

        for _, value in all_data.items():
            epoch_data = json.loads(value)
            for record in epoch_data:
                user = record['stake_address']
                total_reward = Decimal(record['reward'])
                user_rewards[user] += total_reward

        json_data = json.dumps({k: int(v) for k, v in user_rewards.items()})
        redis.set('final_reward', json_data)

    def gen_epoch_reward(self, epoch):
        cache_data = redis.hget('epoch_reward', "epoch.%s" % epoch)
        if cache_data:
            log.info("SKIP | gen_epoch_reward | epoch=%s", epoch)
            return

        log.info('gen_epoch_reward|epoch=%s', epoch)
        pool_records = self.fetch_pools(epoch)
        smallest_pool_id = None
        if pool_records and len(pool_records) > 0:
            smallest_pool_id = pool_records[0]['pool_id']

        # get last delegation <= epoch
        map_addr = {}
        for d in self.get_delegation():
            if d['epoch_no'] > epoch:
                continue
            if d['addr_id'] not in map_addr:
                map_addr[d['addr_id']] = d
            else:
                if map_addr[d['addr_id']]['epoch_no'] < d['epoch_no']:
                    map_addr[d['addr_id']] = d
        result = []

        def _worker(k):
            try:
                stake = EpochStake.objects.filter(addr_id=k, epoch_no=epoch + 2).first()
                _total = stake.amount if stake else 0
                smallest = stake and smallest_pool_id and smallest_pool_id == stake.pool_id
                _v = map_addr[k]
                _v['total_delegate'] = int(_total)
                _v['smallest'] = smallest
                _v['point'] = self.get_point(_total, _v['smallest'])
                result.append(_v)
                if settings.DEBUG:
                    log.info('gen_epoch_reward|r|addr_id=%s|d=%s|point=%s|smallest=%s',
                             k, int(_total), _v['point'], smallest)
            except:
                log.exception('gen_epoch_reward|worker|failed|epoch_no=%s|addr_id=%s|', epoch, k)

        pool = ThreadPool(5)
        pool.map(_worker, map_addr.keys())
        pool.close()
        pool.join()
        total_point = sum([r['point'] for r in result])
        log.info('gen_epoch_reward|total_point=%s', total_point)
        for r in result:
            percent = Decimal(r['point']) / total_point
            reward = round_down(Decimal(self.reward_per_epoch) * percent)
            percent = round_down(percent)
            r['percent'] = str(percent)
            r['reward'] = str(reward)

        output = []
        map_address = self.get_map_address()
        for d in result:
            r = OrderedDict()
            r['epoch'] = epoch
            r['stake_address'] = map_address[d['addr_id']]
            r['stake_address_id'] = d['addr_id']
            r['pool_hash_id'] = str(d['pool_hash_id'])
            r['total_delegate'] = d['total_delegate']
            r['point'] = d['point']
            r['percent'] = round(float(d['percent']) * 100, 4)
            r['reward'] = round(float(d['reward']), 4)
            r['smallest'] = 1 if d['smallest'] else 0
            output.append(r)

        json_output = json.dumps(output)
        redis.hset('epoch_reward', "epoch.%s" % epoch, json_output)

    def gen_seeds(self):
        key = 'epoch.%s.%s' % (self.epoch_start, self.epoch_end)
        result = redis.hget('gen_seeds', key)
        if result:
            return json.loads(result)

        DelegationInfo = namedtuple('DelegationInfo', ['addr_id', 'pool_id', 'epoch_no', 'time', 'block_no'])
        pool_ids = ','.join([str(p) for p in self.get_pool_ids()])
        with connection.cursor() as cursor:
            raw_query = GEN_SEED_QUERY.format(
                pool_ids=pool_ids,
                start_epoch=self.epoch_start + 2,
                end_epoch=self.epoch_end + 2,
            )
            if settings.DEBUG:
                log.info('gen_seeds|raw_query=%s', raw_query)
            cursor.execute(raw_query)
            rows = [DelegationInfo(*r) for r in cursor.fetchall()]

        seeds = []
        for r in rows:
            seeds.append({
                'addr_id': r.addr_id,
                'pool_id': r.pool_id,
                'epoch_no': r.epoch_no,
                'time': r.time.strftime('%Y-%m-%d %H:%M:%S'),
                'block_no': r.block_no,
            })

        result = json.dumps(seeds)
        redis.hset('gen_seeds', key, result)
        return seeds

    def fetch_pools(self, epoch):
        key = 'key.%s' % epoch
        result = redis.hget('get_pools', key)
        if result:
            return json.loads(result)

        log.info("fetch_pools|epoch=%s", epoch)
        first_block = Block.objects.filter(epoch_no=epoch).order_by('id').first()
        last_tx = Tx.objects.filter(block_id=first_block.id).order_by('-id').first()

        pools = []
        for pool_id in self.get_pool_ids():
            log.info("fetching_pools|pool_id=%s", pool_id)
            with connection.cursor() as cursor:
                raw_query = STAKE_QUERY.format(pool_id=pool_id, max_tx=last_tx.id)
                cursor.execute(raw_query)
                stake_address_ids = [r[0] for r in cursor.fetchall()]

            total_stakes = []

            def _worker(batch_stake_address_ids):
                with connection.cursor() as cursor:
                    raw_query = TOTAL_STAKE_QUERY.format(
                        stake_addr_ids=','.join([str(p) for p in batch_stake_address_ids]),
                        max_tx=last_tx.id,
                        last_block=first_block.time,
                        epoch=epoch,
                    )
                    if settings.DEBUG:
                        log.info('fetch_pools|raw_query=%s', raw_query)
                    cursor.execute(raw_query)

                    try:
                        _total_stake = int(cursor.fetchone()[0])
                        total_stakes.append(_total_stake)
                    except TypeError:
                        log.error('get_pools|pool_not_exists|raw_query=%s', raw_query)
                        return

            pool = ThreadPool(10)
            batches = []
            for start, end in split_array_index(len(stake_address_ids), 20):
                batch = stake_address_ids[start:end]
                batches.append(batch)

            pool.map(_worker, batches)
            pool.close()
            pool.join()
            total_stake = sum(total_stakes)
            pools.append({
                'pool_id': pool_id,
                'total_stake': total_stake,
            })

        pools = sorted(pools, key=lambda r: r['total_stake'])
        result = json.dumps(pools)
        redis.hset('get_pools', key, result)
        return pools
