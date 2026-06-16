import base64

from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers

from users.models import User


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name', 'password'
        )


class CustomUserSerializer(BaseUserSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta(BaseUserSerializer.Meta):
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar'
        )

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return obj.subscribers.filter(user=user).exists()


class UserWithRecipesSerializer(CustomUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True
    )

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + (
            'recipes', 'recipes_count'
        )

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit', 3) if request else 3
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 3
        recipes = obj.recipes.all()[:limit]
        # Возвращаем данные вручную, без импорта RecipeMinifiedSerializer
        return [
            {
                'id': recipe.id,
                'name': recipe.name,
                'image': recipe.image.url if recipe.image else None,
                'cooking_time': recipe.cooking_time,
            }
            for recipe in recipes
        ]


class SetAvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('avatar',)

    def update(self, instance, validated_data):
        avatar_data = validated_data['avatar']
        if isinstance(avatar_data, list):
            avatar_data = avatar_data[0]
        if not isinstance(avatar_data, str) or not avatar_data.startswith(
            'data:image'
        ):
            raise serializers.ValidationError('Неверный формат изображения')
        fmt, imgstr = avatar_data.split(';base64,')
        ext = fmt.split('/')[-1]
        file = ContentFile(base64.b64decode(imgstr), name=f'avatar.{ext}')
        instance.avatar = file
        instance.save()
        return instance
