from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Subscription

# Регистрируем модель User с стандартным UserAdmin
admin.site.register(User, UserAdmin)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'author', 'created_at')
    search_fields = ('user__email', 'author__email')
    list_filter = ('created_at',)
