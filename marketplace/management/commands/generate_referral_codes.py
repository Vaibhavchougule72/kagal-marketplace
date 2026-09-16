from django.core.management.base import BaseCommand

from marketplace.models import Customer
from marketplace.views import generate_referral_code


class Command(BaseCommand):
    help = "Generate referral codes for existing customers who do not have one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show customers missing referral codes without changing the database.",
        )

    def handle(self, *args, **options):

        customers = Customer.objects.filter(
            referral_code__isnull=True
        ) | Customer.objects.filter(
            referral_code=""
        )

        total = customers.count()

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "All customers already have referral codes."
                )
            )
            return

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {total} customers are missing referral codes."
                )
            )

            for customer in customers:
                self.stdout.write(
                    f"Missing: {customer.phone} - {customer.name}"
                )

            self.stdout.write(
                self.style.SUCCESS(
                    "No database changes were made."
                )
            )
            return

        updated = 0

        for customer in customers:
            customer.referral_code = generate_referral_code(
                customer.name
            )
            customer.save(update_fields=["referral_code"])
            updated += 1

            self.stdout.write(
                f"Generated referral code for {customer.phone}: "
                f"{customer.referral_code}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated {updated} referral codes."
            )
        )