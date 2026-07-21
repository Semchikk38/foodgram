# Foodgram — Продуктовый помощник

[![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python)](https://python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green?logo=django)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.14-red?logo=django)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13-blue?logo=postgresql)](https://www.postgresql.org/)
[![Nginx](https://img.shields.io/badge/Nginx-1.25-green?logo=nginx)](https://nginx.org/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-22.0-darkgreen?logo=gunicorn)](https://gunicorn.org/)
[![Docker](https://img.shields.io/badge/Docker-24-blue?logo=docker)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-2-blue?logo=docker)](https://docs.docker.com/compose/)
[![Let's Encrypt](https://img.shields.io/badge/SSL-Let's_Encrypt-brightgreen?logo=letsencrypt)](https://letsencrypt.org/)

##  Описание проекта
«Фудграм» — онлайн-сервис для публикации рецептов. Пользователи могут создавать собственные рецепты, добавлять чужие рецепты в избранное, подписываться на понравившихся авторов и формировать автоматический список покупок с суммированием ингредиентов.

##  Демо-версия
Проект развёрнут и доступен по адресу:  
[https://foodgram.servequake.com](https://foodgram.servequake.com)

##  Технологический стек
- **Backend:** Python 3.10, Django 4.2 LTS, Django REST Framework  
- **База данных:** PostgreSQL 13  
- **Веб-сервер:** Nginx + Gunicorn  
- **Контейнеризация:** Docker, Docker Compose  
- **Безопасность:** Let's Encrypt SSL (HTTPS)  
- **CI/CD:** GitHub Actions (настраивается дополнительно)

##  Основные возможности
- Регистрация и аутентификация по токенам (Djoser)
- Управление рецептами: создание, редактирование, удаление
- Система тегов и ингредиентов с поиском по началу названия
- Добавление в избранное и список покупок
- Скачивание списка покупок в формате `.txt` с объединением ингредиентов
- Подписка на авторов и отображение ленты подписок
- Короткие ссылки на рецепты (копирование в буфер обмена)
- Административная панель Django с расширенными возможностями

##  Роли и доступ
| Функционал                                          | Гость | Пользователь | Администратор |
|-----------------------------------------------------|:-----:|:------------:|:-------------:|
| Просмотр рецептов, тегов, профилей                  |   ✅   |      ✅      |       ✅      |
| Регистрация / вход                                   | Регистрация |    Вход     |       —       |
| Создание / редактирование своих рецептов            |   ❌   |      ✅      |     ✅ (все)   |
| Добавление в избранное и покупки                    |   ❌   |      ✅      |       ✅      |
| Выгрузка списка покупок (.txt)                      |   ❌   |      ✅      |       ✅      |
| Подписка на авторов                                 |   ❌   |      ✅      |       ✅      |
| Копирование короткой ссылки                         |   ✅   |      ✅      |       ✅      |
| Управление пользователями и тегами                  |   ❌   |      ❌      |       ✅      |

##  Локальный запуск (без Docker)
```bash
git clone https://github.com/Semchik38/foodgram.git
cd foodgram/backend
python -m venv venv
source venv/bin/activate          # Linux / Mac
venv\Scripts\activate             # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py load_ingredients  # загрузить ингредиенты
python manage.py createsuperuser
python manage.py runserver
```

##  Запуск в Docker
1. Убедитесь, что установлены Docker и Docker Compose.  
2. Создайте файл `backend/.env` со следующим содержимым:
```ini
DB_ENGINE=django.db.backends.postgresql
DB_NAME=django
POSTGRES_USER=django_user
POSTGRES_PASSWORD=ваш_пароль_к_БД
POSTGRES_DB=django
DB_HOST=db
DB_PORT=5432
SECRET_KEY=ваш_секретный_ключ
DEBUG=False
ALLOWED_HOSTS=foodgram.servequake.com,158.160.187.115
```
3. В папке `infra` выполните:
```bash
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py load_ingredients
docker compose exec backend python manage.py collectstatic --noinput
docker compose exec backend python manage.py createsuperuser
```
4. Сайт будет доступен по адресу https://foodgram.servequake.com.

##  Настройка HTTPS
Для получения SSL-сертификата использовался Let's Encrypt:
```bash
sudo certbot certonly --standalone -d foodgram.servequake.com
```
После получения сертификатов в nginx.conf и docker-compose.yml были внесены соответствующие изменения.

## Документация API
OpenAPI-спецификация доступна по адресу /api/docs/ (Redoc).

### Автор:  
_Семён Ерошевич_<br>
**email**: _semchik.er@gmail.com_<br>
**GitHub** [![Semchikk38](https://img.shields.io/badge/Semchikk38-green)](https://github.com/Semchikk38) 

[![Reviewed by EugeneSal](https://img.shields.io/badge/Reviewed_by-EugeneSal-brightgreen)](https://github.com/EugeneSal)


