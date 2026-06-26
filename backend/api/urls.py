from api.views import (
    CustomUserViewSet,
    IngredientViewSet,
    RecipeViewSet,
    ShortLinkRedirectView,
    TagViewSet,
)
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('ingredients', IngredientViewSet)
router.register('tags', TagViewSet)
router.register('recipes', RecipeViewSet, basename='recipe')

urlpatterns = [
    path('users/avatar/', CustomUserViewSet.as_view({
        'patch': 'avatar',
        'put': 'avatar',
        'delete': 'delete_avatar'
    }), name='user-avatar'),
    path('users/me/avatar/', CustomUserViewSet.as_view({
        'patch': 'avatar',
        'put': 'avatar',
        'delete': 'delete_avatar'
    }), name='user-avatar-me'),
    path('users/subscriptions/',
         CustomUserViewSet.as_view({'get': 'subscriptions'}),
         name='user-subscriptions'),
    path('s/<int:short_id>/', ShortLinkRedirectView.as_view(),
         name='short-link'),
    path('users/<int:id>/subscribe/', CustomUserViewSet.as_view({
        'post': 'subscribe',
        'delete': 'subscribe'
    }), name='user-subscribe'),
    path('auth/', include('djoser.urls.authtoken')),
    path('', include('djoser.urls')),
    path('', include(router.urls)),
]
