-- Read-only выгрузка задач бота tg-work-bot для tools/tasks_mirror.py.
-- Один JSON-массив; столбцы берутся как есть (to_jsonb), поэтому запрос
-- работает и до выката RC E (нет колонки project), и после.
-- Открытые задачи + закрытые/отменённые за последние 14 дней.
SELECT COALESCE(json_agg(row), '[]'::json)
FROM (
  SELECT to_jsonb(t)
         || jsonb_build_object(
              'assignee_name', m.display_name,
              'author_name',   a.display_name,
              'chat_title',    c.title
            ) AS row
  FROM tasks t
  LEFT JOIN team_members m ON m.id = t.assignee_member_id
  LEFT JOIN team_members a ON a.id = t.author_member_id
  LEFT JOIN chats c        ON c.id = t.chat_id
  WHERE t.status = 'open'
     OR t.completed_at >= now() - interval '14 days'
     OR t.cancelled_at >= now() - interval '14 days'
  ORDER BY t.status, t.due_at NULLS LAST, t.id
) s;
