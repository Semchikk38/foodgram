import base64
import io
import time

from api.filters import RecipeFilter
from api.pagination import PageNumberPagination
from api.serializers import (
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeListSerializer,
    RecipeMinifiedSerializer,
    SetAvatarSerializer,
    TagSerializer,
    UserSerializer,
    UserWithRecipesSerializer,
)
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        name = request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeListSerializer
        if self.action == 'create':
            return RecipeCreateUpdateSerializer
        if self.action == 'update':
            return RecipeCreateUpdateSerializer
        if self.action == 'partial_update':
            return RecipeCreateUpdateSerializer
        return RecipeListSerializer

    def get_queryset(self):
        queryset = Recipe.objects.all()
        if self.action == 'list':
            queryset = queryset.select_related(
                'author').prefetch_related('tags', 'ingredients')
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        if request.method == 'POST':
            if Favorite.objects.filter(
                    user=request.user,
                    recipe=recipe).exists():
                return Response({'detail': 'Рецепт уже в избранном.'},
                                status=status.HTTP_400_BAD_REQUEST)
            Favorite.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeMinifiedSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            favorite = Favorite.objects.filter(
                user=request.user, recipe=recipe)
            if not favorite.exists():
                return Response({'detail': 'Рецепта нет в избранном.'},
                                status=status.HTTP_400_BAD_REQUEST)
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        if request.method == 'POST':
            if ShoppingCart.objects.filter(
                    user=request.user, recipe=recipe).exists():
                return Response({'detail': 'Рецепт уже в списке покупок.'},
                                status=status.HTTP_400_BAD_REQUEST)
            ShoppingCart.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeMinifiedSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            cart_item = ShoppingCart.objects.filter(
                user=request.user, recipe=recipe)
            if not cart_item.exists():
                return Response({'detail': 'Рецепта нет в списке покупок.'},
                                status=status.HTTP_400_BAD_REQUEST)
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({'detail': 'Необходима авторизация.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        cart_items = ShoppingCart.objects.filter(
            user=user).select_related('recipe')
        if not cart_items:
            return Response({'detail': 'Список покупок пуст.'},
                            status=status.HTTP_404_NOT_FOUND)

        ingredients = (
            RecipeIngredient.objects .filter(
                recipe__in_shopping_cart__user=user) .values(
                'ingredient_id',
                'ingredient__name',
                'ingredient__measurement_unit') .annotate(
                total_amount=Sum('amount')) .order_by('ingredient__name'))

        output = io.StringIO()
        output.write('Список покупок:\n\n')
        for item in ingredients:
            name = item['ingredient__name']
            unit = item['ingredient__measurement_unit']
            amount = item['total_amount']
            output.write(f"{name} ({unit}) — {amount}\n")

        response = HttpResponse(output.getvalue(), content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename=shopping_list.txt'
        )
        return response

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_id = recipe.pk
        return Response({
            'short-link': request.build_absolute_uri(f'/s/{short_id}')
        })


class ShortLinkView(View):
    def get(self, request, short_id):
        recipe = get_object_or_404(Recipe, pk=short_id)
        return redirect(request.build_absolute_uri(f'/recipes/{recipe.pk}/'))


class CustomUserViewSet(DjoserUserViewSet):
    pagination_class = PageNumberPagination
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_serializer_class(self):
        if self.action == 'me':
            return SetAvatarSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        subscriptions = Subscription.objects.filter(
            user=user).select_related('author')
        authors = [sub.author for sub in subscriptions]
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = UserWithRecipesSerializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = UserWithRecipesSerializer(
            authors, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'])
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, id=id)
        user = request.user
        if user == author:
            return Response({'detail': 'Нельзя подписаться на себя.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'POST':
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(
                    {'detail': 'Вы уже подписаны на этого автора.'},
                    status=status.HTTP_400_BAD_REQUEST)
            Subscription.objects.create(user=user, author=author)
            serializer = UserWithRecipesSerializer(
                author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        else:
            subscription = Subscription.objects.filter(
                user=user, author=author)
            if not subscription.exists():
                return Response({'detail': 'Вы не подписаны на этого автора.'},
                                status=status.HTTP_400_BAD_REQUEST)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['patch', 'put'], url_path='avatar')
    def avatar(self, request):
        user = request.user
        avatar_file = request.FILES.get('avatar')
        avatar_data = request.data.get('avatar')

        if avatar_file:
            user.avatar.save(avatar_file.name, avatar_file, save=True)
        elif avatar_data and isinstance(
            avatar_data, str
        ) and avatar_data.startswith('data:image'):
            try:
                format, imgstr = avatar_data.split(';base64,')
                ext = format.split('/')[-1]
                avatar_file = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'avatar_{user.id}_{int(time.time())}.{ext}'
                )
                user.avatar.save(avatar_file.name, avatar_file, save=True)
            except Exception:
                return Response(
                    {'error': 'Неверный формат изображения'}, status=400)
        else:
            return Response({'error': 'Не передан файл'}, status=400)

        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['delete'], url_path='avatar')
    def delete_avatar(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete()
            user.avatar = None
            user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


ShortLinkRedirectView = ShortLinkView
