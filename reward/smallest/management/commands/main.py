from django.core.management.base import BaseCommand

from smallest.lib import IsoManager


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--pool-list',
            nargs='+',
            type=str,
            help='List of pools as strings',
            required=True,
        )
        parser.add_argument(
            '--start-epoch',
            type=int,
            help='Start epoch',
            required=True,
        )
        parser.add_argument(
            '--end-epoch',
            type=int,
            help='End epoch',
            required=True,
        )
        parser.add_argument(
            '--total-reward',
            type=int,
            help='Total reward',
            required=True,
        )
        parser.add_argument(
            '--smallest-bonus',
            type=int,
            help='Smallest bonus'
        )
        parser.add_argument(
            '--whale-limiter',
            type=int,
            help='Whale limiter',
        )

    def handle(self, *args, **kwargs):
        pool_list = kwargs['pool_list']
        start_epoch = kwargs['start_epoch']
        end_epoch = kwargs['end_epoch']
        total_reward = kwargs['total_reward']
        smallest_bonus = kwargs['smallest_bonus']
        whale_limiter = kwargs['whale_limiter']

        # Output the received arguments for demonstration purposes
        self.stdout.write(self.style.SUCCESS('Pool list: {}'.format(pool_list)))
        self.stdout.write(self.style.SUCCESS('Start epoch: {}'.format(start_epoch)))
        self.stdout.write(self.style.SUCCESS('End epoch: {}'.format(end_epoch)))
        self.stdout.write(self.style.SUCCESS('Total reward: {}'.format(total_reward)))
        self.stdout.write(self.style.SUCCESS('Smallest bonus: {}'.format(smallest_bonus)))
        self.stdout.write(self.style.SUCCESS('Whale limiter: {}'.format(whale_limiter)))

        iso_manager = IsoManager(
            pools=pool_list,
            epoch_start=start_epoch,
            epoch_end=end_epoch,
            total_reward=total_reward,
            smallest_bonus=smallest_bonus,
            whale_limiter=whale_limiter,
        )
        iso_manager.build_rewards()

        self.stdout.write(self.style.SUCCESS("ALL DONE!"))
