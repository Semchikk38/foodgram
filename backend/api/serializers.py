import base64
import time

from django.core.files.base import ContentFile
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


class RecipeIngredientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit', read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Количество должно быть больше 0")
        return value


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, read_only=True, source='recipe_ingredients')
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
        return user.is_authenticated and obj.favorites.filter(
            user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        return user.is_authenticated and obj.in_shopping_cart.filter(
            user=user).exists()

    def validate_ingredients(self, value):
        for item in value:
            amount = item.get('amount', 0)
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Количество должно быть числом")
            if amount <= 0:
                raise serializers.ValidationError(
                    "Количество ингредиента должно быть больше 0")
        return value


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = serializers.ListField(
        child=serializers.DictField(),
        write_only=True
    )
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all()
    )
    image = serializers.CharField(allow_blank=True, required=False)

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
        for item in value:
            amount = item.get('amount', 0)
            try:
                amount = int(amount)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Количество должно быть числом")
            if amount <= 0:
                raise serializers.ValidationError(
                    "Количество ингредиента должно быть больше 0")
        return value

    def create(self, validated_data, **kwargs):
        ingredients_data = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        image_data = validated_data.pop('image', None)
        if image_data:
            try:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                user_id = self.context["request"].user.id
                timestamp = int(time.time())
                filename = f'recipe_{user_id}_{timestamp}.{ext}'
                validated_data['image'] = ContentFile(
                    base64.b64decode(imgstr),
                    name=filename
                )
            except (ValueError, TypeError):
                pass
        author = kwargs.get('author') or self.context['request'].user
        validated_data['author'] = author
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        for ingr in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingr['id'],
                amount=ingr['amount']
            )
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags = validated_data.pop('tags', None)
        image_data = validated_data.pop('image', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags is not None:
            instance.tags.set(tags)

        if ingredients_data is not None:
            existing = {
                ri.ingredient_id: ri
                for ri in instance.recipe_ingredients.all()
            }
            new_ids = set()

            for ingr_data in ingredients_data:
                ing_id = ingr_data.get('id')
                amount = ingr_data.get('amount', 0)
                if not ing_id:
                    continue
                if amount <= 0:
                    raise serializers.ValidationError(
                        "Количество ингредиента должно быть больше 0")
                new_ids.add(ing_id)
                if ing_id in existing:
                    ri = existing[ing_id]
                    ri.amount = amount
                    ri.save()
                else:
                    RecipeIngredient.objects.create(
                        recipe=instance,
                        ingredient_id=ing_id,
                        amount=amount
                    )

            for ing_id, ri in existing.items():
                if ing_id not in new_ids:
                    ri.delete()

        if image_data:
            try:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                instance.image = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'recipe_{instance.id}_{int(time.time())}.{ext}'
                )
            except (ValueError, TypeError):
                instance.image = image_data

        instance.save()
        return instance


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


RecipeListSerializer = RecipeSerializer


class SetAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('avatar',)


class UserWithRecipesSerializer(UserSerializer):
    recipes = RecipeMinifiedSerializer(many=True, read_only=True)
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ('id', 'user', 'author', 'created_at')
