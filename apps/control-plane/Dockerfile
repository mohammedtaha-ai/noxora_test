FROM php:8.3-cli-alpine

RUN apk add --no-cache postgresql-dev libzip-dev oniguruma-dev libxml2-dev \
    && docker-php-ext-install pdo_pgsql pgsql mbstring xml zip bcmath

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
WORKDIR /app
