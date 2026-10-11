from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from marketplace.models import Category, SubCategory


SUBCATEGORY_MAP = {
    "Breakfast & Chinese": [
        "Rice",
        "Noodle",
        "Starters",
        "Chinese",
        "Breakfast",
        "Roti",
        "Main Course",
        "Thali",
        "Dal",
    ],
    "Icecream & Shakes": [
        "Ice-creams",
        "Shakes",
        "Soda",
        "Lassi and Rabdi",
        "Mocktails",
    ],
    "Cafe Snacks": [
        "Pizza",
        "Fries",
        "Momos",
        "Maggie",
        "Nuggets",
        "Rolls",
        "Pasta",
        "Sandwiches",
        "Beverages",
        "Burgers",
    ],
    "Meals": [
        "Main-course",
        "Starters",
        "Roti",
        "Rice",
    ],
    "Chat & Bhel": [
        "Maggie",
        "Bhel",
        "Chat",
    ],
}


class Command(BaseCommand):
    help = "Create predefined LOKA product subcategories."

    def handle(self, *args, **options):
        missing_categories = [
            name
            for name in SUBCATEGORY_MAP
            if not Category.objects.filter(name=name).exists()
        ]

        if missing_categories:
            raise CommandError(
                "Missing categories: "
                + ", ".join(missing_categories)
                + ". No subcategories were created."
            )

        created_count = 0
        existing_count = 0

        with transaction.atomic():
            for category_name, names in SUBCATEGORY_MAP.items():
                category = Category.objects.get(name=category_name)

                for priority, name in enumerate(names, start=1):
                    _, created = SubCategory.objects.get_or_create(
                        category=category,
                        name=name,
                        defaults={
                            "priority": priority,
                            "is_active": True,
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created: {created_count}; "
                f"already existed: {existing_count}"
            )
        )