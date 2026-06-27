from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.views import (IngredientViewSet, RecipeViewSet, ShortLinkView,
                       TagViewSet, UserViewSet)

router = DefaultRouter()
router.register('ingredients', IngredientViewSet)
router.register('tags', TagViewSet)
router.register('recipes', RecipeViewSet, basename='recipe')

urlpatterns = [
    path('users/me/', UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('users/avatar/', UserViewSet.as_view({
        'patch': 'avatar',
        'put': 'avatar',
        'delete': 'delete_avatar'
    }), name='user-avatar'),
    path('users/me/avatar/', UserViewSet.as_view({
        'patch': 'avatar',
        'put': 'avatar',
        'delete': 'delete_avatar'
    }), name='user-me-avatar'),
    path('users/subscriptions/',
         UserViewSet.as_view({'get': 'subscriptions'}),
         name='user-subscriptions'),
    path('users/<int:id>/subscribe/', UserViewSet.as_view({
        'post': 'subscribe',
        'delete': 'delete_subscribe'
    }), name='user-subscribe'),

    path('auth/', include('djoser.urls.authtoken')),
    path('', include('djoser.urls')),

    path('s/<int:short_id>/', ShortLinkView.as_view(), name='short-link'),

    path('', include(router.urls)),
]
