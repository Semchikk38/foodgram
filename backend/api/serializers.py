import base64
import time
from django.core.files.base import ContentFile
from django.db import transaction
from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
from rest_framework import serializers
from users.models import Subscription, User


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'avatar',
            'is_subscribed')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(
                user=request.user, author=obj).exists()
        return False


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


# Сериализатор для ЧТЕНИЯ ингредиентов внутри рецепта
class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    # Важно: возвращаем ID самого ингредиента, а не связи
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


# Сериализатор для ЗАПИСИ ингредиентов (только ID и количество)
class IngredientWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    def validate_id(self, value):
        if not Ingredient.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Ингредиент с ID {value} не существует.")
        return value


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для отображения рецепта (GET)"""
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    # Используем правильный source, который совпадает с related_name в модели
    ingredients = RecipeIngredientReadSerializer(many=True, source='recipe_ingredients')
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time')

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.favorites.filter(user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_shopping_cart.filter(user=user).exists()


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецепта (POST/PATCH/PUT)"""
    ingredients = IngredientWriteSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)
    image = serializers.CharField(required=False) # Для обработки base64

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'ingredients',
            'name',
            'image',
            'text',
            'cooking_time')

    def validate_ingredients(self, value):
        ingredient_ids = [item['id'] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError("Ингредиенты должны быть уникальными.")
        return value

    def _save_ingredients(self, recipe, ingredients_data):
        """Вспомогательный метод для сохранения ингредиентов"""
        # Удаляем все старые связи
        recipe.recipe_ingredients.all().delete()
        
        # Создаем новые связи
        bulk_list = []
        for item in ingredients_data:
            bulk_list.append(
                RecipeIngredient(
                    recipe=recipe,
                    ingredient_id=item['id'],
                    amount=item['amount']
                )
            )
        if bulk_list:
            RecipeIngredient.objects.bulk_create(bulk_list)

    @transaction.atomic
    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        image_data = validated_data.pop('image', None)

        # Обработка изображения
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            try:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                filename = f'recipe_{self.context["request"].user.id}_{int(time.time())}.{ext}'
                validated_data['image'] = ContentFile(base64.b64decode(imgstr), name=filename)
            except Exception:
                pass

        recipe = Recipe.objects.create(author=self.context['request'].user, **validated_data)
        recipe.tags.set(tags)
        self._save_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags = validated_data.pop('tags', None)
        image_data = validated_data.pop('image', None)

        # Обновление простых полей
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Обработка изображения
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            try:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                filename = f'recipe_{instance.id}_{int(time.time())}.{ext}'
                instance.image = ContentFile(base64.b64decode(imgstr), name=filename)
            except Exception:
                pass
        
        instance.save()

        if tags is not None:
            instance.tags.set(tags)

        if ingredients_data is not None:
            self._save_ingredients(instance, ingredients_data)

        return instance

    def to_representation(self, instance):
        """При возвращении ответа используем сериализатор для чтения"""
        serializer = RecipeReadSerializer(instance, context=self.context)
        return serializer.data


# Алиасы для совместимости с вашими views.py
RecipeSerializer = RecipeReadSerializer
RecipeListSerializer = RecipeReadSerializer


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SetAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('avatar',)


class UserWithRecipesSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)
    author_page_url = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count', 'author_page_url')

    def get_recipes(self, obj):
        return RecipeMinifiedSerializer(obj.recipes.all()[:3], many=True).data

    def get_author_page_url(self, obj):
        return f'/authors/{obj.id}/'


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ('id', 'user', 'author', 'created_at')


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name', 'last_name')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
