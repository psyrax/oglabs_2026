Title: Persistencia y observabilidad: del SQLite operacional al Postgres analítico
Date: 2026-05-07
Category: blog
Slug: persistencia-sqlite-postgres

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 7 de 8

---

Los agentes generan datos. Muchos datos. Artículos scrapeados, resúmenes generados,
eventos de TCG, reportes de torneos. La pregunta es: ¿cómo persistes todo eso de forma
que sea útil tanto para el agente (lecturas rápidas, escrituras frecuentes) como para
el analista (consultas SQL, dashboards, análisis histórico)?

Nuestra respuesta: **SQLite como fuente de verdad operacional, Postgres como replica
analítica con sync incremental**.

---

## El problema de los dos mundos

Un agente que corre en producción necesita:
- Escrituras rápidas sin latencia de red
- Lecturas simples por key o por fecha
- Sin dependencias externas (funciona aunque el servidor Postgres esté caído)

Un científico de datos que analiza el sistema necesita:
- SQL estándar con JOINs complejos
- Tipos de datos ricos (timestamps, arrays, JSON)
- Conectores para herramientas BI (Metabase, Superset, DBeaver)
- Acceso remoto sin montar un túnel SSH

SQLite satisface el primer conjunto de necesidades. Postgres satisface el segundo.
Intentar usar un solo sistema para ambos significa comprometer en ambos frentes.

---

## Arquitectura del sync

```
┌──────────────────────────────────────┐
│  Raspberry Pi                        │
│                                      │
│  Agente escribe → SQLite             │
│  tools.db                            │
│  ├── news_items (4253 filas hoy)     │
│  ├── cdmx_events                     │
│  ├── gaming_items                    │
│  ├── intl_headlines                  │
│  ├── maker_items                     │
│  └── ... (11 tablas)                 │
│                                      │
│  Columna: synced_at (watermark)      │
│  Trigger: →NULL en cada UPDATE       │
└──────────────────┬───────────────────┘
                   │  sync_all_to_pg.py
                   │  (post send-all, ~1s)
                   ▼
┌──────────────────────────────────────┐
│  Postgres 18 (Docker)                │
│  192.168.1.100:5432                  │
│                                      │
│  DB: openclaw                        │
│  ├── id BIGSERIAL PK (interno)       │
│  ├── source_id (= SQLite rowid)      │
│  ├── columnas espejo                 │
│  ├── synced_at TIMESTAMPTZ           │
│  └── updated_at (trigger automático) │
└──────────────────────────────────────┘
```

---

## El mecanismo de watermark

El sync incremental no requiere `updated_at` en SQLite (que habría que mantener manualmente).
En cambio, usamos una columna `synced_at`:

- **NULL** → la fila tiene cambios no sincronizados (pendiente de sync)
- **timestamp** → la fila fue sincronizada en ese momento y no ha cambiado desde

Un trigger SQLite pone `synced_at = NULL` cada vez que cualquier columna de datos cambia:

```sql
-- Trigger en SQLite (creado por sync_setup.py)
CREATE TRIGGER news_items_dirty
AFTER UPDATE OF title, url, content, summary ON news_items
FOR EACH ROW
WHEN NEW.synced_at IS NOT NULL
BEGIN
    UPDATE news_items SET synced_at = NULL WHERE rowid = NEW.rowid;
END;
```

Nótese el `WHEN NEW.synced_at IS NOT NULL`: esto evita que el trigger se dispare
infinitamente cuando el propio script de sync hace `UPDATE ... SET synced_at = ?`.

El proceso de sync es entonces muy simple:

```python
# sync_all_to_pg.py — lógica core
rows = sqlite_conn.execute(
    "SELECT * FROM news_items WHERE synced_at IS NULL"
).fetchall()

for batch in chunks(rows, size=500):
    pg_conn.execute("""
        INSERT INTO news_items (source_id, title, url, content, ...)
        VALUES %s
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            ...
    """, batch)

# Marcar como sincronizadas
sqlite_conn.execute(
    "UPDATE news_items SET synced_at = ? WHERE rowid IN (?)",
    [now(), [row["rowid"] for row in rows]]
)
```

---

## Schema de Postgres: enriquecido vs espejo

Las tablas en Postgres no son copias exactas del schema SQLite. Están enriquecidas:

```sql
CREATE TABLE news_items (
    -- Clave interna de Postgres (no correlaciona con SQLite)
    id          BIGSERIAL PRIMARY KEY,
    
    -- Clave del registro en SQLite (trazabilidad)
    source_id   BIGINT,
    
    -- Columnas espejo de SQLite
    url         TEXT NOT NULL,
    title       TEXT,
    content     TEXT,
    summary     TEXT,
    source      TEXT,
    fetched_at  TEXT,
    block_reason TEXT,
    
    -- Metadatos de sync (solo en Postgres)
    synced_at   TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Índices para consultas analíticas típicas
CREATE INDEX ON news_items (source, fetched_at DESC);
CREATE INDEX ON news_items (block_reason) WHERE block_reason IS NOT NULL;
CREATE INDEX ON news_items (updated_at DESC);

-- Trigger automático para updated_at
CREATE TRIGGER set_updated_at
BEFORE UPDATE ON news_items
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## Registry declarativo: añadir una tabla en 3 pasos

El setup de sync está diseñado para ser fácil de extender. Un archivo central
`tools/lib/sync.py` declara todas las tablas:

```python
TABLES: list[TableSync] = [
    TableSync(
        name="news_items",
        columns=["url", "title", "content", "summary", "source", "fetched_at", "block_reason"],
        key_columns=["url"],          # ON CONFLICT target
        update_columns=["title", "content", "summary", "block_reason"],
        has_local_id=True,            # SQLite tiene id INTEGER PK → source_id en PG
        pg_types={"fetched_at": "TIMESTAMPTZ"}  # override de tipo
    ),
    TableSync(
        name="cdmx_events",
        columns=["event_name", "venue", "date", "format", "url"],
        key_columns=["event_name", "date", "venue"],
        has_local_id=False,
    ),
    # ... 9 tablas más
]
```

Para añadir una tabla nueva:

```bash
# 1. Añadir TableSync al registry en sync.py
# 2. Aplicar cambios
python3 tools/sync_setup.py

# 3. Listo — el próximo run sube las filas existentes
python3 tools/sync_all_to_pg.py --tables nueva_tabla
```

---

## Consultas analíticas que esto habilita

Con los datos en Postgres puedes hacer preguntas que serían lentas o imposibles en SQLite:

```sql
-- ¿Cuántos artículos tiene contenido completo por fuente?
SELECT source,
       COUNT(*) total,
       COUNT(content) con_contenido,
       ROUND(100.0 * COUNT(content) / COUNT(*), 1) pct_contenido
FROM news_items
WHERE fetched_at > now() - interval '7 days'
GROUP BY source
ORDER BY pct_contenido DESC;

-- ¿Qué tipos de bloqueadores encontramos?
SELECT block_reason, COUNT(*) as ocurrencias
FROM news_items
WHERE block_reason IS NOT NULL
GROUP BY block_reason;

-- Tendencia de artículos por día
SELECT date_trunc('day', synced_at) as dia,
       source,
       COUNT(*) as articulos
FROM news_items
GROUP BY 1, 2
ORDER BY 1 DESC;
```

---

## Tolerancia a fallos

El script de sync siempre termina con `exit 0` (vía wrapper `noticias-sync-pg.sh`).
Si Postgres está caído, el script loguea el error y continúa. Las filas con `synced_at = NULL`
se subirán en el próximo run.

```bash
# noticias-sync-pg.sh
python3 tools/sync_all_to_pg.py >> ~/.openclaw/logs/sync-pg.log 2>&1 || true
```

Esto refleja una filosofía importante: **el sync es best-effort, no crítico**. El agente
sigue funcionando aunque Postgres esté caído. Los datos no se pierden; se sincronizan
en la próxima oportunidad.

---

## Performance baseline

Con ~5,500 filas al inicio y ~100 filas nuevas por día:

| Operación | Tiempo |
|-----------|--------|
| Push inicial (4,253 filas news_items) | 2.3s (~1,856 rows/s) |
| Push inicial (resto de tablas, 1,307 filas) | 0.2s (~6,300 rows/s) |
| Push incremental típico (~100 filas) | <0.5s |

El overhead del sync es insignificante comparado con el scraping y la inferencia con Ollama.

---

*Siguiente: [Lecciones aprendidas y patrones reusables →](06-lecciones.md)*
