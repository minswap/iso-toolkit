from django.db import models
from django.db.models import QuerySet
from django.db.models.manager import BaseManager


class MyQuerySet(QuerySet):
    def __init__(self, *args, **kwargs):
        super(MyQuerySet, self).__init__(*args, **kwargs)

    def pk_list(self):
        return list(self.values_list("pk", flat=True))

    def flat_list(self, field, distinct=False):
        qs = self.values_list(field, flat=True)
        qs = qs.distinct() if distinct else qs
        return list(qs)

    def batch_iter(self, batch_size=2000):
        total = self.count()
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            yield self[start:end]


class Manager(BaseManager.from_queryset(MyQuerySet)):
    pass


class ModelBase(models.Model):
    objects = Manager()

    class Meta:
        abstract = True


class PoolHash(models.Model):
    objects = Manager()

    id = models.BigIntegerField(primary_key=True)
    view = models.CharField(max_length=255)

    class Meta:
        db_table = 'pool_hash'


class StakeAddress(ModelBase):
    id = models.BigIntegerField(primary_key=True)
    view = models.CharField(max_length=255)

    class Meta:
        db_table = 'stake_address'


class Delegation(ModelBase):
    id = models.BigIntegerField(primary_key=True)
    addr_id = models.BigIntegerField()
    pool_hash_id = models.BigIntegerField()
    active_epoch_no = models.BigIntegerField()
    tx_id = models.BigIntegerField()

    class Meta:
        db_table = 'delegation'


class EpochStake(models.Model):
    id = models.BigIntegerField(primary_key=True)
    addr_id = models.BigIntegerField()
    pool_id = models.BigIntegerField()
    amount = models.BigIntegerField()
    epoch_no = models.BigIntegerField()

    class Meta:
        db_table = 'epoch_stake'


class TxOut(ModelBase):
    id = models.BigIntegerField(primary_key=True)
    stake_address_id = models.BigIntegerField()
    address = models.CharField(max_length=255)
    tx_id = models.BigIntegerField()
    value = models.BigIntegerField()

    class Meta:
        db_table = 'tx_out'


class Block(models.Model):
    id = models.BigIntegerField(primary_key=True)
    time = models.DateTimeField()
    epoch_no = models.BigIntegerField()

    class Meta:
        db_table = 'block'


class Tx(models.Model):
    id = models.BigIntegerField(primary_key=True)
    block_id = models.BigIntegerField()

    class Meta:
        db_table = 'tx'


class Treasury(models.Model):
    id = models.BigIntegerField(primary_key=True)
    amount = models.BigIntegerField()
    addr_id = models.BigIntegerField()
    tx_id = models.BigIntegerField()

    class Meta:
        db_table = 'treasury'
        unique_together = ('addr_id', 'tx_id')


class Reserve(models.Model):
    id = models.BigIntegerField(primary_key=True)
    amount = models.BigIntegerField()
    addr_id = models.BigIntegerField()
    tx_id = models.BigIntegerField()

    class Meta:
        db_table = 'reserve'
        unique_together = ('addr_id', 'tx_id')


class Reward(models.Model):
    id = models.BigIntegerField(primary_key=True)
    addr_id = models.BigIntegerField()
    type = models.CharField(max_length=100)
    amount = models.BigIntegerField()
    pool_id = models.BigIntegerField()
    earned_epoch = models.BigIntegerField()
    spendable_epoch = models.BigIntegerField()

    class Meta:
        db_table = 'reward'
        unique_together = ('addr_id', 'type', 'earned_epoch', 'pool_id')


class MinDelegation(models.Model):
    id = models.BigIntegerField(primary_key=True)
    stake_address = models.CharField(max_length=64)
    addr_id = models.BigIntegerField()
    pool_hash_id = models.BigIntegerField()
    active_epoch_no = models.BigIntegerField()
    tx_id = models.BigIntegerField()
    epoch_no = models.BigIntegerField()
    time = models.DateTimeField()

    class Meta:
        db_table = 'min_delegation'
