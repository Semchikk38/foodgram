import io

from django.db import models
from django.db.models import Count, Exists, OuterRef, Sum, Value
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.filters import IngredientFilter, RecipeFilter
from api.pagination import PageNumberPagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    FavoriteSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeMinifiedSerializer,
    RecipeReadSerializer,
    SetAvatarSerializer,
    ShoppingCartSerializer,
    SubscriptionSerializer,
    TagSerializer,
    UserSerializer,
    UserWithRecipesSerializer,
)
from recipes.models import Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingCart, Tag
from users.models import Subscription, User


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
    filterset_class = IngredientFilter


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = PageNumberPagination

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        queryset = Recipe.objects.select_related('author').prefetch_related(
            'tags', 'recipe_ingredients'
        )
        if user and user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(user=user, recipe=OuterRef('pk'))
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(user=user, recipe=OuterRef('pk'))
                ),
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=models.BooleanField()),
                is_in_shopping_cart=Value(False, output_field=models.BooleanField()),
            )
        return queryset

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        return RecipeCreateUpdateSerializer

    def _add_relation(self, request, pk, model, serializer_class):
        recipe = get_object_or_404(Recipe, pk=pk)
        data = {'user': request.user.id, 'recipe': recipe.id}
        serializer = serializer_class(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _delete_relation(self, request, pk, model):
        deleted, _ = model.objects.filter(user=request.user, recipe_id=pk).delete()
        if not deleted:
            return Response(
                {'detail': 'Объект не найден'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,)
    )
    def favorite(self, request, pk=None):
        return self._add_relation(request, pk, Favorite, FavoriteSerializer)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return self._delete_relation(request, pk, Favorite)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,)
    )
    def shopping_cart(self, request, pk=None):
        return self._add_relation(request, pk, ShoppingCart, ShoppingCartSerializer)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return self._delete_relation(request, pk, ShoppingCart)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,)
    )
    def download_shopping_cart(self, request):
        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_cart__user=request.user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')
        if not ingredients:
            return Response(
                {'detail': 'Список покупок пуст'},
                status=status.HTTP_404_NOT_FOUND
            )
        content = self._format_shopping_list(ingredients)
        response = FileResponse(
            io.BytesIO(content.encode('utf-8')),
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename=shopping_list.txt'
        return response

    @staticmethod
    def _format_shopping_list(items):
        output = io.StringIO()
        output.write('Список покупок:\n\n')
        for item in items:
            name = item['ingredient__name']
            unit = item['ingredient__measurement_unit']
            amount = item['total_amount']
            output.write(f'{name} ({unit}) — {amount}\n')
        return output.getvalue()

    @action(detail=True, methods=('get',), url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        return Response({
            'short-link': request.build_absolute_uri(
                reverse('short-link', args=[recipe.pk])
            )
        })


class ShortLinkView(View):
    def get(self, request, short_id):
        try:
            recipe = Recipe.objects.get(pk=short_id)
            return redirect(
                request.build_absolute_uri(f'/recipes/{recipe.pk}/')
            )
        except Recipe.DoesNotExist:
            return redirect(request.build_absolute_uri('/not_found'))


class UserViewSet(DjoserUserViewSet):
    pagination_class = PageNumberPagination
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    @action(detail=False, methods=('get',), permission_classes=(IsAuthenticated,))
    def me(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,)
    )
    def subscriptions(self, request):
        authors = User.objects.filter(
            subscriptions_to_the_author__user=request.user
        ).annotate(
            recipes_count=Count('recipes')
        ).order_by('username')
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = UserWithRecipesSerializer(
                page, many=True, context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = UserWithRecipesSerializer(
            authors, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,)
    )
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
        deleted, _ = Subscription.objects.filter(
            user=request.user, author_id=id
        ).delete()
        if not deleted:
            return Response(
                {'detail': 'Вы не подписаны на этого автора'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=('put',),
        permission_classes=(IsAuthenticated,),
        url_path='me/avatar',
        url_name='me/avatar'
    )
    def me_avatar(self, request):
        serializer = SetAvatarSerializer(
            request.user,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            UserSerializer(request.user, context={'request': request}).data
        )

    @me_avatar.mapping.delete
    def delete_me_avatar(self, request):
        request.user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
