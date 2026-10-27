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
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process pending jobs until the queue is empty, then exit.",
        )

    def handle(self, *args, **options):
        interval = max(1, options["interval"])
        run_once = options["once"]

        self.stdout.write(
            self.style.SUCCESS(
                "Notification worker started. "
                + (
                    "Processing pending jobs until the queue is empty."
                    if run_once
                    else f"Polling every {interval} seconds."
                )
            )
        )

        while True:
            try:
                result = process_next_notification_job()

                if result is None:
                    if run_once:
                        self.stdout.write(
                            self.style.SUCCESS(
                                "No pending notification jobs. Worker finished."
                            )
                        )
                        break

                    time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING("Notification worker stopped.")
                )
                break

            except Exception:
                logger.exception(
                    "Notification worker encountered an error."
                )

                if run_once:
                    raise

                time.sleep(interval)
