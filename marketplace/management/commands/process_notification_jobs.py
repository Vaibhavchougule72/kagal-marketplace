import logging
import time

from django.core.management.base import BaseCommand

from marketplace.tasks import process_next_notification_job


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending LOKA notification jobs from PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Seconds to wait when no jobs are pending.",
        )

    def handle(self, *args, **options):
        interval = max(1, options["interval"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Notification worker started. Polling every {interval} seconds."
            )
        )

        while True:
            try:
                result = process_next_notification_job()

                if result is None:
                    time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING("Notification worker stopped.")
                )
                break

            except Exception:
                logger.exception("Notification worker encountered an error.")
                time.sleep(interval)