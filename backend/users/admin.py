from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Subscription, User


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'recipes_count', 'followers_count')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'is_staff')

    def recipes_count(self, obj):
        return obj.recipes.count()
    recipes_count.short_description = 'Рецептов'

    def followers_count(self, obj):
        return obj.subscriptions_to_the_author.count()
    followers_count.short_description = 'Подписчиков'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'author')
    search_fields = ('user__email', 'author__email')
    list_filter = ('user',)
