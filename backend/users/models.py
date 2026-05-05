from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField('email address', unique=True)
    username = models.CharField(
        'username', max_length=150, unique=True,
        error_messages={
            'unique': "Пользователь с таким именем уже существует.",
        },
    )
    first_name = models.CharField('first name', max_length=150)
    last_name = models.CharField('last name', max_length=150)
    avatar = models.ImageField(upload_to='users/', blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.username
