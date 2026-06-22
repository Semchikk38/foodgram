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

from api.filters import RecipeFilter
from api.pagination import PageNumberPagination
from api.serializers import (
    IngredientSerializer,
    RecipeListSerializer,
    RecipeCreateUpdateSerializer,
    RecipeMinifiedSerializer,
    TagSerializer,
    SetAvatarSerializer,
    UserWithRecipesSerializer,
)
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
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
            queryset = queryset.select_related('author').prefetch_related('tags', 'ingredients')
        return queryset


    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post', 'delete'])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        if request.method == 'POST':
            if Favorite.objects.filter(user=request.user, recipe=recipe).exists():
                return Response({'detail': 'Рецепт уже в избранном.'},
                                status=status.HTTP_400_BAD_REQUEST)
            Favorite.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeMinifiedSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            favorite = Favorite.objects.filter(user=request.user, recipe=recipe)
            if not favorite.exists():
                return Response({'detail': 'Рецепта нет в избранном.'},
                                status=status.HTTP_400_BAD_REQUEST)
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'])
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        if request.method == 'POST':
            if ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists():
                return Response({'detail': 'Рецепт уже в списке покупок.'},
                                status=status.HTTP_400_BAD_REQUEST)
            ShoppingCart.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeMinifiedSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            cart_item = ShoppingCart.objects.filter(user=request.user, recipe=recipe)
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

        cart_items = ShoppingCart.objects.filter(user=user).select_related('recipe')
        if not cart_items:
            return Response({'detail': 'Список покупок пуст.'},
                            status=status.HTTP_404_NOT_FOUND)

        cart_recipe_ids = ShoppingCart.objects.filter(user=user).values_list('recipe', flat=True)
        ingredients = (
    	    RecipeIngredient.objects
            .filter(recipe__in=cart_recipe_ids)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )

        output = io.StringIO()
        output.write('Список покупок:\n\n')
        for item in ingredients:
            output.write(
                f"{item['ingredient__name']} ({item['ingredient__measurement_unit']}) — {item['total_amount']}\n"
            )

        response = HttpResponse(output.getvalue(), content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename=shopping_list.txt'
        return response

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_id = recipe.pk
        return Response({'short-link': f'https://{request.get_host()}/s/{short_id}'})


class ShortLinkView(View):
    def get(self, request, short_id):
        recipe = get_object_or_404(Recipe, pk=short_id)
        return redirect('recipe-detail', pk=recipe.pk)


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
        subscriptions = Subscription.objects.filter(user=user).select_related('author')
        authors = [sub.author for sub in subscriptions]
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = UserWithRecipesSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = UserWithRecipesSerializer(authors, many=True, context={'request': request})
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
                return Response({'detail': 'Вы уже подписаны на этого автора.'},
                                status=status.HTTP_400_BAD_REQUEST)
            Subscription.objects.create(user=user, author=author)
            serializer = UserWithRecipesSerializer(author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        else:  # DELETE
            subscription = Subscription.objects.filter(user=user, author=author)
            if not subscription.exists():
                return Response({'detail': 'Вы не подписаны на этого автора.'},
                                status=status.HTTP_400_BAD_REQUEST)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
ShortLinkRedirectView = ShortLinkView
