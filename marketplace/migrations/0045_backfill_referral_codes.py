from django.db import migrations
import random
import string


def generate_unique_referral_code(Customer, name):
    prefix = "".join(
        char for char in (name or "").upper()
        if char.isalnum()
    )[:3]

    prefix = prefix.ljust(3, "X")

    while True:
        suffix = "".join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

        code = f"{prefix}{suffix}"

        if not Customer.objects.filter(
            referral_code=code
        ).exists():
            return code


def backfill_referral_codes(apps, schema_editor):
    Customer = apps.get_model("marketplace", "Customer")

    customers = Customer.objects.filter(
        referral_code__isnull=True
    ) | Customer.objects.filter(
        referral_code=""
    )

    for customer in customers:
        customer.referral_code = generate_unique_referral_code(
            Customer,
            customer.name
        )
        customer.save(
            update_fields=["referral_code"]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "marketplace",
            "0044_order_loka_money_used_pendingorder_loka_money_used",
        ),
    ]

    operations = [
        migrations.RunPython(
            backfill_referral_codes,
            migrations.RunPython.noop,
        ),
    ]