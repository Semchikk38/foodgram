import io
from django.db.models import Exists, OuterRef, Sum, Value, BooleanField, Count, Prefetch
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.filters import RecipeFilter
from api.pagination import PageNumberPagination
from api.serializers import (
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeMinifiedSerializer,
    RecipeReadSerializer,
    SetAvatarSerializer,
    SubscriptionSerializer,
    TagSerializer,
    UserSerializer,
    UserWithRecipesSerializer,
)
from recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
from users.models import Subscription, User

from .permissions import IsAuthorOrReadOnly


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    permission_classes = (permissions.AllowAny,)
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('name',)

    def list(self, request, *args, **kwargs):
        """Переопределяем list для поддержки поиска по началу строки"""
        queryset = self.get_queryset()
        name = request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.select_related(
        'author').prefetch_related('tags', 'recipe_ingredients')
    permission_classes = (IsAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = PageNumberPagination

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        queryset = super().get_queryset()

        # Аннотируем только если есть авторизованный пользователь
        if user and user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(Favorite.objects.filter(
                    user=user, recipe=OuterRef('pk'))),
                is_in_shopping_cart=Exists(ShoppingCart.objects.filter(
                    user=user, recipe=OuterRef('pk'))),
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField()),
            )
        return queryset

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        return RecipeCreateUpdateSerializer

    @action(detail=True, methods=('post',), permission_classes=(IsAuthenticated,))
    def favorite(self, request, pk=None):
        return self._manage_relation(request, pk, Favorite, 'Рецепт уже в избранном', 'Рецепта нет в избранном')

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return self._manage_relation(request, pk, Favorite, 'Рецепт уже в избранном', 'Рецепта нет в избранном', delete=True)

    @action(detail=True, methods=('post',), permission_classes=(IsAuthenticated,))
    def shopping_cart(self, request, pk=None):
        return self._manage_relation(request, pk, ShoppingCart, 'Рецепт уже в списке покупок', 'Рецепта нет в списке покупок')

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return self._manage_relation(request, pk, ShoppingCart, 'Рецепт уже в списке покупок', 'Рецепта нет в списке покупок', delete=True)

    def _manage_relation(self, request, pk, model, exists_msg, not_exists_msg, delete=False):
        recipe = get_object_or_404(Recipe, pk=pk)
        obj = model.objects.filter(user=request.user, recipe=recipe)

        if delete:
            if not obj.exists():
                return Response({'detail': not_exists_msg}, status=status.HTTP_400_BAD_REQUEST)
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if obj.exists():
            return Response({'detail': exists_msg}, status=status.HTTP_400_BAD_REQUEST)

        model.objects.create(user=request.user, recipe=recipe)
        return Response(RecipeMinifiedSerializer(recipe).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=('get',), permission_classes=(IsAuthenticated,))
    def download_shopping_cart(self, request):
        recipe_ids = ShoppingCart.objects.filter(
            user=request.user).values_list('recipe_id', flat=True)
        if not recipe_ids:
            return Response({'detail': 'Список покупок пуст'}, status=status.HTTP_404_NOT_FOUND)

        ingredients = (
            RecipeIngredient.objects
            .filter(recipe_id__in=recipe_ids)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )
        output = io.StringIO()
        output.write('Список покупок:\n\n')
        for item in ingredients:
            output.write(
                f"{item['ingredient__name']} ({item['ingredient__measurement_unit']}) — {item['total_amount']}\n")

        response = FileResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename=shopping_list.txt'
        return response

    @action(detail=True, methods=('get',), url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        return Response({'short-link': request.build_absolute_uri(f'/s/{recipe.pk}')})


class ShortLinkView(View):
    def get(self, request, short_id):
        try:
            recipe = Recipe.objects.get(pk=short_id)
            return redirect(request.build_absolute_uri(f'/recipes/{recipe.pk}/'))
        except Recipe.DoesNotExist:
            return redirect(request.build_absolute_uri('/not_found'))


class UserViewSet(DjoserUserViewSet):
    pagination_class = PageNumberPagination
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def me(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=('get',), permission_classes=(IsAuthenticated,))
    def subscriptions(self, request):
        authors = User.objects.filter(
            following__user=request.user
        ).annotate(
            recipes_count=Count('recipes')
        ).prefetch_related(
            Prefetch('recipes', queryset=Recipe.objects.all()
                     [:3], to_attr='limited_recipes')
        )
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = UserWithRecipesSerializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = UserWithRecipesSerializer(
            authors, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=('post',), permission_classes=(IsAuthenticated,))
    def subscribe(self, request, id=None):
        serializer = SubscriptionSerializer(
            data={'user': request.user.id, 'author': id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def delete_subscribe(self, request, id=None):
        subscription = Subscription.objects.filter(
            user=request.user, author_id=id)
        if not subscription.exists():
            return Response({'detail': 'Вы не подписаны на этого автора'}, status=status.HTTP_400_BAD_REQUEST)
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=('patch', 'put'), permission_classes=(IsAuthenticated,))
    def avatar(self, request):
        user = request.user
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
            user.save()
            return Response(UserSerializer(user, context={'request': request}).data)
        serializer = SetAvatarSerializer(
            user, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user, context={'request': request}).data)

    @action(detail=False, methods=('delete',), permission_classes=(IsAuthenticated,))
    def delete_avatar(self, request):
        if request.user.avatar:
            request.user.avatar.delete()
            request.user.avatar = None
            request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=('put', 'patch'), permission_classes=(IsAuthenticated,))
    def update_me(self, request):
        user = request.user
        serializer = UserSerializer(
            user, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
