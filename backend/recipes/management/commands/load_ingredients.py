import json

from django.core.management.base import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Load ingredients from data/ingredients.json'

    def handle(self, *args, **options):
        try:
            with open('data/ingredients.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(
                'File data/ingredients.json not found'))
            return

        ingredients = [
            Ingredient(
                name=item['name'], measurement_unit=item['measurement_unit'])
            for item in data
        ]

        created = Ingredient.objects.bulk_create(
            ingredients, ignore_conflicts=True)
        self.stdout.write(
            self.style.SUCCESS(
                f'Loaded {len(created)} new ingredients (duplicates ignored)')
        )
