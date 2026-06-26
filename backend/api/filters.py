from django_filters import rest_framework as filters
from recipes.models import Recipe, Tag


class RecipeFilter(filters.FilterSet):
    tags = filters.CharFilter(method='filter_tags')

    author = filters.NumberFilter(field_name='author__id')

    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('tags', 'author', 'is_favorited', 'is_in_shopping_cart')

    def filter_tags(self, queryset, name, value):
        slugs = self.request.query_params.getlist('tags')

        if not slugs:
            return queryset

        valid_slugs = Tag.objects.filter(slug__in=slugs).values_list(
            'slug', flat=True)

        if not valid_slugs:
            return queryset.none()

        return queryset.filter(tags__slug__in=valid_slugs).distinct()

    def filter_is_favorited(self, queryset, name, value):
        if not value:
            return queryset
        user = self.request.user
        if user.is_authenticated:
            return queryset.filter(favorites__user=user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if not value:
            return queryset
        user = self.request.user
        if user.is_authenticated:
            return queryset.filter(in_shopping_cart__user=user)
        return queryset
