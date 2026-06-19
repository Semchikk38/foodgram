from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'author', 'created_at')
    search_fields = ('user__email', 'author__email')
    list_filter = ('created_at',)
