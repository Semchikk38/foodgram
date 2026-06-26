from django_filters import rest_framework as filters
from recipes.models import Recipe, Tag


class RecipeFilter(filters.FilterSet):
    tags = filters.CharFilter(field_name='tags__slug', method='filter_tags')
    author = filters.NumberFilter(field_name='author__id')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')

    class Meta:
        model = Recipe
        fields = ('tags', 'author', 'is_favorited', 'is_in_shopping_cart')

    def filter_tags(self, queryset, name, value):
        request = getattr(self, 'request', None)
        if request:
            slugs = request.query_params.getlist('tags')
            if slugs:
                existing_slugs = Tag.objects.filter(
                    slug__in=slugs
                ).values_list('slug', flat=True)
                if set(slugs) - set(existing_slugs):
                    return queryset.none()
                for slug in slugs:
                    queryset = queryset.filter(tags__slug=slug)
                return queryset
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        if not value:
            return queryset
        user = getattr(self.request, 'user', None) if hasattr(
            self, 'request'
        ) else None
        if user and user.is_authenticated:
            return queryset.filter(favorites__user=user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if not value:
            return queryset
        user = getattr(self.request, 'user', None) if hasattr(
            self, 'request'
        ) else None
        if user and user.is_authenticated:
            return queryset.filter(in_shopping_cart__user=user)
        return queryset
