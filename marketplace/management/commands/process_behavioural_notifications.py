import logging
import time

from marketplace.behavioural_notifications.scheduler import (
    discover_and_schedule_behavioural_notifications,
)

from django.core.management.base import BaseCommand

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

    def handle(self, *args, **options):

        interval = max(1, options["interval"])

        self.stdout.write(
            self.style.SUCCESS(
                "LOKA Behavioural Notification Worker Started."
            )
        )

        self.stdout.write(
            f"Polling interval: {interval} seconds."
        )

        while True:

            try:

                # First discover and schedule new customer activities.
                discover_and_schedule_behavioural_notifications()

                # Then send notifications that are due.
                processed = process_behavioural_notification_batch()

                if processed:

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Processed {processed} notifications."
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