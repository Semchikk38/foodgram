from django.urls import include, path
from recipes.views import (IngredientViewSet, RecipeViewSet,
                           SubscriptionViewSet, TagViewSet)
from rest_framework.routers import DefaultRouter
from users.views import AvatarViewSet

router = DefaultRouter()
router.register('ingredients', IngredientViewSet)
router.register('tags', TagViewSet)
router.register('recipes', RecipeViewSet)

urlpatterns = [
    path('users/subscriptions/',
         SubscriptionViewSet.as_view({'get': 'subscriptions'})),
    path('users/<int:id>/subscribe/',
         SubscriptionViewSet.as_view({
             'post': 'subscribe', 'delete': 'unsubscribe'
         })),
    path('users/me/avatar/', AvatarViewSet.as_view()),

    path('auth/', include('djoser.urls.authtoken')),
    path('', include('djoser.urls')),
    path('', include(router.urls)),
]
