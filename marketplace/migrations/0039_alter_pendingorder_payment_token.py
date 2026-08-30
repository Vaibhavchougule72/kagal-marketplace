import uuid

from django.db import migrations, models


def fix_duplicate_payment_tokens(apps, schema_editor):
    PendingOrder = apps.get_model("marketplace", "PendingOrder")

    # Find all payment tokens that appear more than once
    duplicate_tokens = (
        PendingOrder.objects
        .values("payment_token")
        .annotate(count=models.Count("id"))
        .filter(count__gt=1)
    )

    for item in duplicate_tokens:
        token = item["payment_token"]

        # Keep the first record unchanged
        orders = PendingOrder.objects.filter(
            payment_token=token
        ).order_by("id")

        first = True

        for order in orders:
            if first:
                first = False
                continue

            # Generate a new unique token
            new_token = uuid.uuid4()

            while PendingOrder.objects.filter(
                payment_token=new_token
            ).exists():
                new_token = uuid.uuid4()

            order.payment_token = new_token
            order.save(
                update_fields=["payment_token"]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0038_alter_pendingorder_payment_token"),
    ]

    operations = [
        migrations.RunPython(
            fix_duplicate_payment_tokens,
            migrations.RunPython.noop,
        ),

        migrations.AlterField(
            model_name="pendingorder",
            name="payment_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                null=True,
                blank=True,
            ),
        ),
    ]