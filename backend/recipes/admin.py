from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count

from .models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1

    def clean(self):
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get(
                'DELETE', False
            ):
                amount = form.cleaned_data.get('amount', 0)
                if amount <= 0:
                    raise ValidationError(
                        "Количество ингредиента должно быть больше 0"
                    )
        return super().clean()


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'favorite_count')
    search_fields = ('name', 'author__email', 'author__username')
    list_filter = ('tags',)
    inlines = [RecipeIngredientInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            fav_count=Count('favorites'))

    def favorite_count(self, obj):
        return obj.fav_count
    favorite_count.short_description = 'В избранном'


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


admin.site.register(Favorite)
admin.site.register(ShoppingCart)
