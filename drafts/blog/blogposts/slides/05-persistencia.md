---
marp: true
theme: uncover
class: invert
paginate: true
style: |
  section {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 1.1rem;
  }
  section.title {
    text-align: center;
  }
  h1 { color: #7dd3fc; }
  h2 { color: #86efac; border-bottom: 1px solid #334155; padding-bottom: 0.3em; }
  code { background: #1e293b; color: #f8fafc; padding: 0.1em 0.4em; border-radius: 4px; }
  pre  { background: #0f172a; border-left: 3px solid #7dd3fc; }
  table { font-size: 0.85rem; }
  th { background: #1e3a5f; color: #7dd3fc; }
  .small { font-size: 0.8rem; }
---

<!-- class: title -->
# Persistencia y observabilidad
## SQLite → Postgres: sync incremental

---

## El problema de los dos mundos

| Necesidad | Solución |
|-----------|----------|
| Escrituras rápidas sin latencia de red | SQLite local |
| Sin dependencias externas (funciona offline) | SQLite local |
| SQL estándar con JOINs complejos | Postgres |
| Conectores BI (Metabase, DBeaver) | Postgres |
| Acceso remoto sin SSH | Postgres |

> SQLite = fuente de verdad operacional
> Postgres = replica analítica

---

## El mecanismo de watermark

```sql
-- Trigger en SQLite: pone synced_at = NULL en cada mutación
CREATE TRIGGER news_items_dirty
AFTER UPDATE OF title, url, content, summary ON news_items
FOR EACH ROW
WHEN NEW.synced_at IS NOT NULL  -- evita loop infinito
BEGIN
    UPDATE news_items SET synced_at = NULL WHERE rowid = NEW.rowid;
END;
```

- `synced_at IS NULL` → pendiente de sync
- `synced_at = timestamp` → sincronizada, sin cambios

No necesita `updated_at`. Se mantiene solo.

---

## El sync en código

```python
# Solo filas con cambios
rows = sqlite.execute(
    "SELECT * FROM news_items WHERE synced_at IS NULL"
).fetchall()

# Upsert en Postgres
pg.execute(
    "INSERT INTO news_items (source_id, url, title, content, ...)"
    " VALUES %s ON CONFLICT (url) DO UPDATE SET"
    " content = EXCLUDED.content ...",
    rows
)

# Marcar como sincronizadas
sqlite.execute(
    "UPDATE news_items SET synced_at = ? WHERE rowid IN (?)",
    [now(), [r["rowid"] for r in rows]]
)
```

---

## Registry declarativo

```python
TABLES = [
    TableSync(
        name="news_items",
        columns=["url", "title", "content", "summary", ...],
        key_columns=["url"],
        has_local_id=True,
    ),
    TableSync(
        name="cdmx_events",
        columns=["event_name", "venue", "date", "format", "url"],
        key_columns=["event_name", "date", "venue"],
    ),
    # ... 9 tablas más
]
```

Añadir una tabla nueva: editar `sync.py` → `python3 sync_setup.py` → listo.

---

## Consultas analíticas que esto habilita

```sql
-- Cobertura de contenido por fuente (última semana)
SELECT source,
       COUNT(*) total,
       ROUND(100.0 * COUNT(content) / COUNT(*), 1) pct_contenido
FROM news_items
WHERE fetched_at > now() - interval '7 days'
GROUP BY source ORDER BY pct_contenido DESC;

-- Tipos de bloqueadores encontrados
SELECT block_reason, COUNT(*) FROM news_items
WHERE block_reason IS NOT NULL
GROUP BY block_reason;
```

---

## Performance baseline

| Operación | Tiempo |
|-----------|--------|
| Push inicial 4,253 filas (news_items) | 2.3 s (~1,856 rows/s) |
| Push inicial 10 tablas restantes (1,307 filas) | 0.2 s |
| Push incremental típico (~100 filas nuevas) | < 0.5 s |

El sync siempre termina con `exit 0` — tolerante a Postgres caído.
Las filas pendientes se sincronizan en el próximo run.
