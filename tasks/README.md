# Задачи — зеркало бота

Создано: 03.10.2026.

**Источник истины по задачам команды — Telegram‑бот `NightAstraeus/tg-work-bot`** (БД Postgres на ноутбуке команды, Mini App). Здесь — только read‑only зеркало для недельного ритма и навыков. `MIRROR.md` и `mirror.json` **руками не править**: следующий запуск скрипта их перезапишет.

## Как обновить зеркало (фаза 1, с мака владельца)
Скрипт `tools/tasks_mirror.py` берёт JSON с задачами из команды, заданной переменной `TASKS_EXPORT_CMD`, и пишет `tasks/MIRROR.md` + `tasks/mirror.json`. Команда должна вывести один JSON‑массив. Пример для текущего стенда (Postgres в WSL на ноутбуке, read‑only SELECT):

```bash
export TASKS_EXPORT_CMD="ssh laptop \"wsl -d Ubuntu-24.04 -u root -- bash -c 'cd /путь/tg-work-bot && docker compose exec -T postgres psql -U \\\$POSTGRES_USER -d \\\$POSTGRES_DB -At -f -'\" < tools/tasks_mirror.sql"
python3 tools/tasks_mirror.py && git add tasks && git commit -m "tasks: зеркало $(date +%d.%m.%Y)"
```

Путь к репе бота на ноутбуке и имя дистрибутива — из `tg-work-bot/AGENTS.md` («Машины»); секреты в env контейнера, в команду не вписываются. Проверка формата без доступа к БД: `python3 tools/tasks_mirror.py --demo`.

До выката RC E в БД нет поля `project` — зеркало выводит задачи без деления на ТОФС/ИНВИКС и пишет об этом в шапке.

## Фазы (решение 03.10.2026, `DECISIONS.md`)
1. **Сейчас** — зеркало через SQL, код бота не трогаем.
2. **После выката RC E–I** — read‑only `GET /export/tasks` в API бота под существующим Bearer‑токеном (как `/chats/{id}/open-tasks`), скрипт переключается с SQL на HTTP. Пакет идёт через очередь и ревью бота («Входящие»), не отсюда.
3. **Через месяц** — оценить, нужен ли обратный канал (комментарий разбора в задачу). По умолчанию — нет.

Зеркало в GitHub Issues и двусторонняя синхронизация отклонены: второе место правки, расхождение статусов.

## Граница
Стратегические вопросы и решения — Issues этой репы. Оперативные задачи — бот. Железо — Issues `printer-config`. Увидел задачу в weekly или Issue — попроси завести в боте и оставь `#id`.
