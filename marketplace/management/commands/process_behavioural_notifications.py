import logging
import time

from django.core.management.base import BaseCommand

from marketplace.behavioural_notifications.scheduler import (
    discover_and_schedule_behavioural_notifications,
)

from marketplace.behavioural_notifications.processor import (
    process_behavioural_notification_batch,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Process scheduled LOKA behavioural notifications."

    def add_arguments(self, parser):

        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Seconds between worker polling cycles."
        )

        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one processing cycle and exit."
        )

    def process_cycle(self):

        # Discover and schedule new customer activities.
        scheduled = discover_and_schedule_behavioural_notifications()

        # Process notifications that are due.
        processed = process_behavioural_notification_batch()

        return scheduled, processed

    def handle(self, *args, **options):

        interval = max(1, options["interval"])
        once = options["once"]

        self.stdout.write(
            self.style.SUCCESS(
                "LOKA Behavioural Notification Worker Started."
            )
        )

        # GitHub Actions mode: execute one cycle and exit.
        if once:

            self.stdout.write("Running one-time processing cycle...")

            try:

                scheduled, processed = self.process_cycle()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cycle completed. Scheduled: {scheduled}, "
                        f"Processed: {processed}."
                    )
                )

            except Exception as e:

                logger.exception(
                    "Behavioural notification one-time processing failed."
                )

                raise e

            return

        # Continuous worker mode.
        self.stdout.write(
            f"Polling interval: {interval} seconds."
        )

        while True:

            try:

                scheduled, processed = self.process_cycle()

                if processed or scheduled:

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Scheduled: {scheduled}, "
                            f"Processed: {processed}."
                        )
                    )

                else:

                    self.stdout.write(
                        "No pending behavioural notifications."
                    )

                time.sleep(interval)

            except KeyboardInterrupt:

                self.stdout.write(
                    self.style.WARNING(
                        "Behavioural notification worker stopped."
                    )
                )

                break

            except Exception:

                logger.exception(
                    "Behavioural notification worker error."
                )

                time.sleep(interval)