#!/usr/bin/env python3
"""Зеркало задач Telegram-бота tg-work-bot → tasks/MIRROR.md + tasks/mirror.json.

Read-only: ничего не пишет в бота. Источник — JSON-массив задач, который
выдаёт команда из переменной окружения TASKS_EXPORT_CMD (обычно psql с
tools/tasks_mirror.sql через ssh, см. tasks/README.md). Поля читаются
мягко: нет колонки project (до выката RC E) — зеркало без проектов.

    tools/tasks_mirror.py            # TASKS_EXPORT_CMD → tasks/
    tools/tasks_mirror.py --demo     # встроенные тестовые данные → tasks/
    tools/tasks_mirror.py --input f.json

Только stdlib. Ошибки — короткие коды без содержимого env и stderr внешних
команд (по образцу tg-work-bot/scripts/publish_github.py).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_MD = ROOT / "tasks" / "MIRROR.md"
OUT_JSON = ROOT / "tasks" / "mirror.json"
TZ = timezone(timedelta(hours=5), "Asia/Yekaterinburg")
PROJECTS = ("ТОФС", "ИНВИКС")
NO_PROJECT = "Без проекта"
FIELDS = (
    "id", "project", "description", "status", "assignee", "author",
    "due_at", "due_has_time", "completed_at", "cancelled_at", "created_at",
    "chat_title",
)

DEMO = [
    {"id": 57, "project": "ИНВИКС", "description": "Закупить профиль для силовой обшивки",
     "status": "open", "assignee_name": "Фанзиль Кунусбаев", "author_name": "Арсений Губенко",
     "due_at": "2026-10-10T00:00:00+00:00", "due_has_time": False, "chat_title": "Инвикс — команда"},
    {"id": 58, "project": "ТОФС", "description": "Собрать второй стенд, прогнать тест камеры",
     "status": "open", "assignee_name": "Дима Макаров", "author_name": "Арсений Губенко",
     "due_at": "2026-10-01T09:00:00+00:00", "due_has_time": True, "chat_title": "Инвикс — команда"},
    {"id": 59, "project": None, "description": "Прислать данные для визиток",
     "status": "open", "assignee": "все", "chat_title": "Инвикс — команда"},
    {"id": 51, "project": "ИНВИКС", "description": "Нарезать Benchy под сопло 0.6",
     "status": "done", "assignee_name": "Арсений Губенко",
     "completed_at": "2026-10-02T14:20:00+00:00", "chat_title": "Инвикс — команда"},
]


def fail(code: str) -> None:
    print(f"tasks_mirror: {code}", file=sys.stderr)
    sys.exit(2)


def load_rows(args: argparse.Namespace) -> list[dict]:
    if args.demo:
        return DEMO
    if args.input:
        raw = Path(args.input).read_text(encoding="utf-8")
    else:
        cmd = os.environ.get("TASKS_EXPORT_CMD")
        if not cmd:
            fail("E_NO_SOURCE (задай TASKS_EXPORT_CMD, --input или --demo)")
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            fail("E_EXPORT_TIMEOUT")
        if proc.returncode != 0:
            fail(f"E_EXPORT_FAILED rc={proc.returncode}")
        raw = proc.stdout
    try:
        rows = json.loads(raw.strip() or "[]")
    except json.JSONDecodeError:
        fail("E_BAD_JSON")
    if not isinstance(rows, list):
        fail("E_NOT_A_LIST")
    return rows


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize(row: dict) -> dict:
    out = {k: row.get(k) for k in FIELDS}
    out["assignee"] = row.get("assignee_name") or row.get("assignee")
    out["author"] = row.get("author_name")
    out["project"] = row.get("project") if row.get("project") in PROJECTS else None
    return out


def fmt_due(task: dict, now: datetime) -> str:
    due = parse_dt(task.get("due_at"))
    if not due:
        return "—"
    local = due.astimezone(TZ)
    text = local.strftime("%d.%m.%Y %H:%M") if task.get("due_has_time") else local.strftime("%d.%m.%Y")
    if task.get("status") == "open":
        # Дата без времени хранится как полночь UTC календарного дня (server/due.py).
        deadline = due if task.get("due_has_time") else due.replace(hour=23, minute=59)
        if deadline < now:
            text += " **просрочено**"
    return text


def render(tasks: list[dict], now: datetime, has_project_column: bool) -> str:
    stamp = now.astimezone(TZ).strftime("%d.%m.%Y %H:%M")
    lines = [
        "# Зеркало задач бота",
        "",
        f"> **Автоматическая копия — не редактировать вручную.** Выгружено: {stamp} (Asia/Yekaterinburg).",
        "> Источник истины — бот `tg-work-bot`. Правила — `tasks/README.md`.",
    ]
    if not has_project_column:
        lines.append("> В БД пока нет поля «проект» (RC E не развёрнут) — задачи без деления на ТОФС/ИНВИКС.")
    lines.append("")
    open_tasks = [t for t in tasks if t.get("status") == "open"]
    closed = [t for t in tasks if t.get("status") != "open"]
    overdue = sum(1 for t in open_tasks if "просрочено" in fmt_due(t, now))
    lines.append(f"Открыто: {len(open_tasks)}, из них просрочено: {overdue}. Закрыто/отменено за 14 дней: {len(closed)}.")
    lines.append("")

    groups = [*PROJECTS, NO_PROJECT] if has_project_column else [NO_PROJECT]
    for group in groups:
        subset = [t for t in open_tasks if (t.get("project") or NO_PROJECT) == group] if has_project_column else open_tasks
        title = group if has_project_column else "Открытые задачи"
        lines += [f"## {title} — {len(subset)}", ""]
        if not subset:
            lines += ["_нет_", ""]
            continue
        lines += ["| # | Задача | Исполнитель | Срок |", "|---|---|---|---|"]
        for t in subset:
            desc = str(t.get("description") or "").replace("|", "¦").replace("\n", " ")
            lines.append(f"| {t['id']} | {desc} | {t.get('assignee') or '—'} | {fmt_due(t, now)} |")
        lines.append("")

    lines += ["## Закрыто и отменено за 14 дней", ""]
    if not closed:
        lines += ["_нет_", ""]
    else:
        lines += ["| # | Задача | Статус | Когда | Исполнитель |", "|---|---|---|---|---|"]
        for t in closed:
            when = parse_dt(t.get("completed_at") or t.get("cancelled_at"))
            when_s = when.astimezone(TZ).strftime("%d.%m.%Y") if when else "—"
            desc = str(t.get("description") or "").replace("|", "¦").replace("\n", " ")
            status = {"done": "готово", "cancelled": "отменена"}.get(t.get("status"), t.get("status"))
            lines.append(f"| {t['id']} | {desc} | {status} | {when_s} | {t.get('assignee') or '—'} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="встроенные тестовые данные")
    ap.add_argument("--input", help="файл с JSON-массивом задач")
    ap.add_argument("--stdout", action="store_true", help="печатать Markdown, файлы не писать")
    args = ap.parse_args()

    rows = load_rows(args)
    has_project_column = any("project" in r for r in rows)
    tasks = [normalize(r) for r in rows if isinstance(r, dict) and "id" in r]
    now = datetime.now(timezone.utc)
    md = render(tasks, now, has_project_column)
    payload = {
        "exported_at": now.isoformat(timespec="seconds"),
        "has_project_column": has_project_column,
        "tasks": tasks,
    }
    if args.stdout:
        print(md)
        return
    OUT_MD.write_text(md + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"tasks_mirror: {len(tasks)} задач → {OUT_MD.relative_to(ROOT)}, {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
