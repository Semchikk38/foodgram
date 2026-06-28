from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count

from .models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1

    def clean(self):
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                amount = form.cleaned_data.get('amount', 0)
                if amount <= 0:
                    raise ValidationError('Количество ингредиента должно быть больше 0')
        return super().clean()


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'favorite_count', 'get_tags', 'get_ingredients')
    search_fields = ('name', 'author__email', 'author__username')
    list_filter = ('tags',)
    inlines = (RecipeIngredientInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(fav_count=Count('favorites'))

    def favorite_count(self, obj):
        return obj.fav_count
    favorite_count.short_description = 'В избранном'

    def get_tags(self, obj):
        return ', '.join([tag.name for tag in obj.tags.all()])
    get_tags.short_description = 'Теги'

    def get_ingredients(self, obj):
        return ', '.join([ri.ingredient.name for ri in obj.recipe_ingredients.all()])
    get_ingredients.short_description = 'Ингредиенты'


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)
    list_filter = ('measurement_unit',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    list_filter = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    search_fields = ('user__email', 'recipe__name')
    list_filter = ('user',)


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe')
    search_fields = ('user__email', 'recipe__name')
    list_filter = ('user',)
