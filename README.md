# Веб‑геоприложение + PostGIS + OSM (St. Petersburg)

Проект демонстрирует полный цикл разработки простого геовеб‑приложения:
1) загрузка данных OpenStreetMap (OSM) в геопространственную БД,
2) пространственные запросы в PostGIS,
3) отображение результатов на веб‑карте.


## Что умеет приложение
- показывает точки интереса (POI) Санкт‑Петербурга на карте (кафе, аптеки, магазины и т.п.)
- фильтрация по категории
- поиск “рядом”:
  - клик по карте → найти объекты в радиусе R метров
  - рисуется круг радиуса
  - кнопка “Сбросить поиск рядом” возвращает режим просмотра по области карты

## Стек технологий
- **База данных:** PostgreSQL + PostGIS
- **Backend:** Python FastAPI
- **Frontend:** React (Vite) + Leaflet
- **Данные:** OpenStreetMap  
  Импорт выполняется через Nominatim (bbox/границы) + Overpass API (POI).  
  (Такой способ выбран, потому что в некоторых сетях PBF/Geofabrik может быть недоступен.)

## Как устроены данные в БД (коротко)
Используются две основные таблицы:
- `places` — точки (Point) с полями `name`, `category`, `address`
- `districts` — полигоны границ (MultiPolygon)


## Пространственные операции (что показывает PostGIS)
- Поиск объектов в пределах области карты (bbox)
- Поиск объектов в радиусе R метров от точки (near search)
- Выдача геоданных в формате GeoJSON для фронтенда

# Запуск проекта

## 1) Запуск базы данных
В корне проекта:
```bash
docker compose up -d db
```

## 2) Импорт данных OSM в PostGIS
Импорт запускается отдельным сервисом importer (профиль import):
```bash
docker compose --profile import up --build importer
```
После импорта можно проверить, что точки действительно появились:

```bash
docker exec -it geoapp-db psql -U geo -d geo -c "select count(*) from places;"
docker exec -it geoapp-db psql -U geo -d geo -c "select distinct category from places order by 1 limit 20;"
```
## 3) Запуск backend + frontend
```bash
docker compose up --build backend frontend
```
Открыть:
- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health

## Перезапуск проекта “с нуля” (полная очистка + импорт заново)
Если нужно удалить все данные и повторить импорт:

```bash
docker compose down -v
docker compose up -d db
docker compose --profile import up --build importer
docker compose up --build backend frontend
```
```-v``` удаляет volumes (включая данные PostgreSQL), поэтому это полный сброс.

## Работа с БД вручную
Подключиться к PostgreSQL в контейнере
```bash
docker exec -it geoapp-db psql -U geo -d geo
```
Полезные команды:
```sql
\dt            -- список таблиц
\d places      -- структура таблицы places
\d districts   -- структура таблицы districts
```

Примеры запросов к данным:

1. Топ категорий по количеству
    ```sql
    SELECT category, count(*)
    FROM places
    GROUP BY category
    ORDER BY count(*) DESC
    LIMIT 30;
    ```

2. Количество точек в bbox
    ```sql
    SELECT count(*)
    FROM places
    WHERE geom && ST_MakeEnvelope(29.98,59.81,30.64,60.06,4326);
    ```
3. Ближайшие 10 точек к заданной координате
    ```sql
    WITH q AS (
    SELECT ST_SetSRID(ST_MakePoint(30.3141,59.9386),4326)::geography AS g
    )
    SELECT name, category,
        round(ST_Distance(p.geog, q.g)::numeric, 1) AS dist_m
    FROM places p, q
    ORDER BY p.geog <-> q.g
    LIMIT 10;
    ```

4. Количество точек в радиусе 500м от заданной координаты
    ```sql
    WITH q AS (
    SELECT ST_SetSRID(ST_MakePoint(30.3141,59.9386),4326)::geography AS g
    )
    SELECT count(*)
    FROM places p, q
    WHERE ST_DWithin(p.geog, q.g, 500);
    ```

5. Точки в радиусе 500м от заданной координаты
    ```sql
    WITH q AS (
    SELECT ST_SetSRID(ST_MakePoint(30.3141,59.9386),4326)::geography AS g
    )
    SELECT count(*)
    FROM places p, q
    WHERE ST_DWithin(p.geog, q.g, 500);
    ```

6. Сколько объектов по каждой категории:
    ```sql
    SELECT category, COUNT(*) AS cnt
    FROM places
    GROUP BY category
    ORDER BY cnt DESC
    LIMIT 30;
    ```

7. Сколько объектов с адресом/без:
    ```sql
    SELECT
    COUNT(*) AS total,
    COUNT(address) AS with_address,
    COUNT(*) - COUNT(address) AS without_address
    FROM places;
    ```

8. Точки в окне + категория:
    ```sql
    SELECT COUNT(*)
    FROM places
    WHERE category = 'cafe'
    AND geom && ST_MakeEnvelope(29.9, 59.8, 30.8, 60.1, 4326);

9. В каком районе находится точка?”
(Если districts загружены)

    ```sql
    SELECT d.name
    FROM districts d
    WHERE ST_Contains(d.geom, ST_SetSRID(ST_MakePoint(30.3141, 59.9386), 4326))
    LIMIT 5;
    ```
