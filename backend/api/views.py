import io

from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from recipes.filters import RecipeFilter
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Subscription, Tag)
from recipes.pagination import CustomPageNumberPagination
from recipes.serializers import (IngredientSerializer,
                                 RecipeCreateUpdateSerializer,
                                 RecipeListSerializer,
                                 RecipeMinifiedSerializer, TagSerializer)
from users.models import User
from users.serializers import SetAvatarSerializer, UserWithRecipesSerializer

from .permissions import IsAuthorOrReadOnly


class ShortLinkRedirectView(View):
    def get(self, request, short_id):
        recipe = get_object_or_404(Recipe, id=short_id)
        return redirect(f'/recipes/{recipe.id}/')


class CustomUserViewSet(DjoserUserViewSet):
    pagination_class = CustomPageNumberPagination

    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        authors = User.objects.filter(subscribers__user=request.user).distinct()
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = UserWithRecipesSerializer(page, many=True,
                                                   context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = UserWithRecipesSerializer(authors, many=True,
                                               context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, pk=id)
        user = request.user
        if user == author:
            return Response(
                {'error': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        _, created = Subscription.objects.get_or_create(user=user, author=author)
        if not created:
            return Response(
                {'error': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = UserWithRecipesSerializer(author,
                                               context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id=None):
        author = get_object_or_404(User, pk=id)
        user = request.user
        deleted, _ = Subscription.objects.filter(user=user, author=author).delete()
        if not deleted:
            return Response(
                {'error': 'Вы не подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar')
    def avatar(self, request):
        if request.method == 'PUT':
            serializer = SetAvatarSerializer(instance=request.user,
                                             data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            avatar_url = request.user.avatar.url if request.user.avatar else None
            return Response({'avatar': avatar_url})
        elif request.method == 'DELETE':
            user = request.user
            if user.avatar:
                user.avatar.delete(save=True)
            user.avatar = None
            user.save(update_fields=['avatar'])
            return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    pagination_class = None
    serializer_class = IngredientSerializer
    filter_backends = (SearchFilter,)
    search_fields = ('^name',)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    pagination_class = None
    serializer_class = TagSerializer


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateUpdateSerializer
        return RecipeListSerializer

    def get_permissions(self):
        if self.action in ('create',):
            return (permissions.IsAuthenticated(),)
        if self.action in ('update', 'partial_update', 'destroy'):
            return (permissions.IsAuthenticated(), IsAuthorOrReadOnly())
        if self.action in ('favorite', 'shopping_cart',
                           'download_shopping_cart'):
            return (permissions.IsAuthenticated(),)
        return (permissions.AllowAny(),)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        _, created = Favorite.objects.get_or_create(user=user, recipe=recipe)
        if not created:
            return Response(
                {'error': 'Рецепт уже в избранном.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = RecipeMinifiedSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        deleted, _ = Favorite.objects.filter(user=user, recipe=recipe).delete()
        if not deleted:
            return Response(
                {'error': 'Рецепта не было в избранном.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        _, created = ShoppingCart.objects.get_or_create(user=user, recipe=recipe)
        if not created:
            return Response(
                {'error': 'Рецепт уже в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = RecipeMinifiedSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        deleted, _ = ShoppingCart.objects.filter(user=user, recipe=recipe).delete()
        if not deleted:
            return Response(
                {'error': 'Рецепта не было в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[permissions.IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_cart__user=user
        ).values(
            name=F('ingredient__name'),
            measurement_unit=F('ingredient__measurement_unit')
        ).annotate(total_amount=Sum('amount')).order_by('ingredient__name')

        if not ingredients:
            return Response(
                {'detail': 'Список покупок пуст.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        content = io.StringIO()
        for item in ingredients:
            content.write(
                f"{item['name']} ({item['measurement_unit']})"
                f" — {item['total_amount']}\n"
            )

        response = HttpResponse(content.getvalue(), content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_url = request.build_absolute_uri(f'/s/{recipe.id}')
        return Response({'short-link': short_url})
