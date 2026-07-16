from django_filters import FilterSet, rest_framework as filters

from recipes.models import Recipe, Tag, Ingredient


class RecipeFilter(FilterSet):
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
        conjoined=False,
    )
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_is_in_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if not value or not self.request or not self.request.user.is_authenticated:
            return queryset
        return queryset.filter(favorite__user=self.request.user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if not value or not self.request or not self.request.user.is_authenticated:
            return queryset
        return queryset.filter(shoppingcart__user=self.request.user)


class IngredientFilter(FilterSet):
    name = filters.CharFilter(method='filter_name')

    def filter_name(self, queryset, name, value):
        return queryset.filter(name__istartswith=value)

    class Meta:
        model = Ingredient
        fields = ('name',)
