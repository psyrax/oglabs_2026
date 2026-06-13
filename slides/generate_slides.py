#!/usr/bin/env python3
"""
Genera slide decks en formato Marp para cada blog post de la serie
"Sistemas Multi-Agente en tu Homelab".
Luego invoca marp-cli vía npx para renderizar HTML.
"""

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).parent / "marp"
OUT.mkdir(exist_ok=True)

MARP_HEADER = """---
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
"""

DECKS: dict[str, str] = {}

# ──────────────────────────────────────────────
# DECK 01 — ¿Por qué un homelab para LLMs?
# ──────────────────────────────────────────────
DECKS["01-por-que-homelab"] = MARP_HEADER + """
<!-- class: title -->
# ¿Por qué un homelab para LLMs?
## Sistemas Multi-Agente — Post 1

Experimentar sin miedo a la factura, con control total.

---

## El problema con "solo cloud"

- 💸 **Costo por token** — una sesión de debugging puede costar $10–30
- 🌐 **Latencia variable** — 20 llamadas encadenadas = 40 s de jitter
- 🔒 **Datos privados** — enviar datos sensibles a un tercero es un bloqueador
- ⛔ **Rate limits** — interrumpen el flujo de iteración rápida
- 📡 **Dependencia de disponibilidad** — si el endpoint cae, tu demo cae

---

## Qué ganas con hardware propio

| Ventaja | Detalle |
|---------|---------|
| Costo marginal = $0 | Itera 500 veces sin pensar en el medidor |
| Latencia predecible | qwen3:0.6b responde en ~200 ms local |
| Modelos especializados | Visión, código, idiomas — sin pedir acceso |
| Contexto completo | Logs, prompts, tokens, tiempos — todo visible |
| Aprendes la infra real | systemd, Docker, watchdogs, backups |

---

## Hardware: no necesitas servidores caros

```
┌──────────────────────┐   ┌────────────────────────┐
│  Raspberry Pi 5      │   │  PC de escritorio      │
│  arm64, ~5W idle     │   │  x86, 8GB VRAM         │
│                      │   │                        │
│  Orquestador         │   │  LLM backend (Ollama)  │
│  Gateway de agentes  │   │  Postgres (Docker)     │
│  Crons, scripts      │   │                        │
└──────────────────────┘   └────────────────────────┘

   Costo eléctrico mensual < una sesión de debugging en GPT-4
```

---

## Cuándo sí usar cloud

No es dogma. Usamos APIs externas cuando:

- Necesitamos un **modelo de frontera** (GPT-4o, Claude Opus)
- El experimento es **one-shot** y montar infra no vale
- Necesitamos **escala horizontal** rápida

**La clave:** tener claridad sobre cuándo cada opción es correcta.

---

## Lo que construiremos en esta serie

```
WhatsApp ──▶ Gateway (OpenClaw) ──▶ Skills especializados
                                         │
                    ┌────────────────────┼────────────────┐
                    ▼                    ▼                ▼
              Noticias MX          Eventos TCG      Meta TCG decks
              Noticias intl        Pokémon del día
              Maker/gaming

              SQLite ──── sync incremental ────▶ Postgres
```
"""

# ──────────────────────────────────────────────
# DECK 02 — Infraestructura
# ──────────────────────────────────────────────
DECKS["02-infraestructura"] = MARP_HEADER + """
<!-- class: title -->
# La infraestructura
## Hardware, servicios y topología

---

## Topología completa

```
Raspberry Pi 5 (arm64)          Servidor LLM (x86)
────────────────────────        ──────────────────────
OpenClaw Gateway :18789         Ollama :11434
Chromium CDP     :18800         ├── qwen3.5:9b
Xvfb :0                         ├── gemma4:e4b
Cron jobs                       ├── qwen2.5vl:3b
SQLite tools.db                 └── gemma4:26b

                                Postgres 18 :5432
                                (Docker)

       ←──── LAN 192.168.50.0/24 ────→
```

---

## Modelo de LLMs por tarea

| Tarea | Modelo | Por qué |
|-------|--------|---------|
| Agente general / routing | `qwen3.5:9b` | Tool use, contexto largo |
| Resúmenes de noticias | `gemma4:e4b` | Rápido, buena síntesis |
| Visión (screenshots) | `qwen2.5vl:3b` | Tarea simple, necesita velocidad |
| Razonamiento complejo | `gemma4:26b` | Alta precisión, latencia aceptable |

> ⚡ No uses el modelo más grande para todo

---

## ¿Por qué SQLite como fuente de verdad?

- **Cero latencia de red** — el proceso escribe en el mismo host
- **Sin servidor** — nada se "cae", sin conexiones que gestionar
- **Backups triviales** — `cp tools.db tools.db.bak`
- **Suficiente para un nodo** — miles de escrituras/día sin problema

```
SQLite (local, fuente de verdad)
    │
    └── sync incremental post-send
    ▼
Postgres (Docker, analítica y BI)
```

---

## Systemd como supervisor de procesos

```ini
[Unit]
Description=OpenClaw Agent Gateway
After=network.target

[Service]
ExecStart=/home/psyrax/.npm-global/bin/openclaw gateway start
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```

- Auto-restart si el proceso crashea
- Logs con `journalctl --user -u openclaw-gateway -f`
- Arranca automáticamente en cada boot

---

## Anti-patrón: no paralelizar todo

```bash
# ❌ MAL — 7 scrapers compitiendo por Ollama + RAM
python3 mexico_noticias.py &
python3 intl_noticias.py &
python3 gaming_noticias.py &
wait

# ✅ BIEN — uno a la vez, predecible
python3 mexico_noticias.py
python3 intl_noticias.py
python3 gaming_noticias.py
```

> El cuello de botella es Ollama, no la orquestación.
> El rendimiento total es similar. El debugging es trivial.
"""

# ──────────────────────────────────────────────
# DECK 03 — OpenClaw
# ──────────────────────────────────────────────
DECKS["03-openclaw"] = MARP_HEADER + """
<!-- class: title -->
# OpenClaw
## El framework de agentes que conecta LLMs con el mundo real

---

## Arquitectura de tres capas

```
Canal (WhatsApp / Telegram / HTTP)
         │  mensajes
         ▼
Gateway  :18789
├── Router: ¿qué skill usar?
├── Context manager: historial
└── LLM fallback (qwen3.5:9b)
         │  invocación
         ▼
Skills
├── mexico-noticias
├── intl-noticias
├── cdmx-tcg-events
├── pokemon-dia
└── tcg-deck-analyst
```

---

## El ciclo de un agente con tool use

```
Usuario: "¿qué noticias hay de tecnología hoy?"
    │
    ▼
LLM (qwen3.5:9b)
  → llama tool: get_news(category="tech", date="today")
    │
    ▼
Tool ejecuta: SELECT * FROM news_items WHERE ...
    │
    ▼
LLM recibe resultados → genera respuesta en lenguaje natural
    │
    ▼
WhatsApp: "Hoy en tecnología: [resumen con links]"
```

---

## Skills: la unidad de capacidad

```
~/.openclaw/workspace/skills/
├── mexico-noticias/
│   └── SKILL.md       ← descripción, triggers, cómo ejecutar
├── cdmx-tcg-events/
│   ├── SKILL.md
│   └── venue_overrides.json
└── tcg-deck-analyst/
    └── SKILL.md
```

Cada skill define:
- **Cuándo activarse** (descripción semántica para el router)
- **Qué comandos ejecutar** y cómo
- **Reglas de formato** de respuesta
- **Qué NO hacer** (muy importante)

---

## WhatsApp como canal de producción

| Ventaja | Detalle |
|---------|---------|
| Fricción cero | No hay app que instalar, no hay login |
| Notificaciones nativas | El agente envía proactivamente |
| Grupos | Múltiples "suscripciones" por audiencia |
| Multimedia | Imágenes, documentos, audio |

```
120363409044388439  →  noti boris  (México + Intl)
120363409682945871  →  make: read  (Maker/hardware)
120363424994533833  →  gaming & tech
120363407680632725  →  Eventos TCG
```

---

## Ollama con API compatible OpenAI

```json
{
  "agents": {
    "defaults": {
      "model": "openai/ollama:qwen3.5:9b",
      "baseURL": "http://192.168.50.113:11434/v1"
    }
  }
}
```

> Cualquier framework que soporte OpenAI SDK
> funciona con Ollama — solo cambia `baseURL` y modelo
"""

# ──────────────────────────────────────────────
# DECK 04 — Agentes de noticias
# ──────────────────────────────────────────────
DECKS["04-agentes-noticias"] = MARP_HEADER + """
<!-- class: title -->
# Agentes de noticias
## Del RSS al resumen con LLM

---

## Pipeline completo

```
Fuentes RSS / Sitios web
    │
    ▼ CDP scraping + RSS parse
news_items (SQLite, sin contenido)
    │
    ▼ Ollama gemma4:e4b
resumen generado (SQLite)
    │
    ▼ 8am / 18pm
WhatsApp groups
    │ post-send
    ▼
fetch articles (CDP + visión VLM)
    │
    ▼
news_items.content (SQLite)
    │
    ▼ sync incremental
Postgres (analítica)
```

---

## Cuatro agentes especializados

| Agente | Fuentes | Método |
|--------|---------|--------|
| `mexico_noticias.py` | Animal Político, La Jornada, El Universal, Milenio, El Financiero, Proceso | CDP |
| `intl_noticias.py` | Reuters, BBC, Al Jazeera, DW, France 24, Guardian, AP, El País | CDP |
| `maker_noticias.py` | Hackaday, Hackster, Make, Adafruit, Arduino, Tom's Hardware | RSS |
| `gaming_noticias.py` | Kotaku, Game Developer, Ars Technica, The Verge, RPS, Eurogamer | RSS |

---

## CDP: Chromium como herramienta de scraping

```python
async def navigate_and_extract(url: str) -> str:
    async with CDPSession(port=18800) as session:
        await session.navigate(url)
        await session.wait_for_load()
        content = await session.evaluate(ARTICLE_EXTRACT_JS)
        return content
```

- Perfiles persistentes por agente → cookies entre sesiones
- Sin `--headless=new` → el modo display real evita detección anti-bot
- Puerto 18800, un browser compartido por todos los scrapers

---

## Manejo anti-bot: el árbol de decisiones

```
Extraer texto del artículo
    │
    ├── len > 100 chars → ✅ guardar
    │
    └── len < 100 chars → tomar screenshot
            │
            ▼ qwen2.5vl:3b (~2-3s)
        Clasificar: cookie_wall | captcha | paywall | login_wall | none
            │
            ├── cookie_wall → dismiss(button_text) → reintentar
            ├── captcha / paywall / login_wall → marcar block_reason (no reintentar)
            └── none / falla → marcar extract_failed (sí reintentar)
```

---

## Cloudflare: RSS como fallback elegante

```python
def parse_feed(url: str) -> list[NewsItem]:
    feed = feedparser.parse(url)
    for entry in feed.entries:
        # Adafruit incluye el artículo completo en el RSS
        content = entry.get("content", [{}])[0].get("value", "")
        items.append(NewsItem(
            url=entry.link,
            content=content if len(content) >= 500 else None
        ))
```

> Antes de pelear con anti-bot, pregunta si hay una API o feed
> que ya tenga los datos. Casi siempre hay una ruta más directa.

---

## El prompt importa: fidelidad sobre creatividad

```
❌ "Resume los temas principales de estas noticias"
   → el modelo genera paráfrasis genéricas, inventa contexto

✅ "Copia los titulares exactos con sus URLs.
    No parafrasees ni inventes."
   → el modelo reproduce titulares reales, sin alucinaciones
```

`num_predict=8000` — los modelos de razonamiento usan tokens
internamente antes de generar la respuesta visible.
Con 3000, el modelo se cortaba a mitad del resumen.

---

## Fetch y send son procesos separados

```
fetch (7am/17pm)    →    SQLite    →    send (8am/18pm)
                             ↑
                       audit trail
                       re-enviable
                       consultable
```

- Si el send falla (WhatsApp down), el fetch ya está hecho
- Puedes re-enviar sin re-scrapear: `SELECT` en DB → mandar
- El fetch tarda 10–30 min; el send es casi instantáneo
- Historial auditado de qué se envió y cuándo
"""

# ──────────────────────────────────────────────
# DECK 05 — Persistencia
# ──────────────────────────────────────────────
DECKS["05-persistencia"] = MARP_HEADER + """
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
"""

# ──────────────────────────────────────────────
# DECK 06 — Lecciones aprendidas
# ──────────────────────────────────────────────
DECKS["06-lecciones"] = MARP_HEADER + """
<!-- class: title -->
# 10 lecciones aprendidas
## Patrones que vienen de fallas reales

---

## 1. Secuencialidad > Paralelismo

```bash
# ❌ 7 scrapers compitiendo por Ollama (una VRAM)
python3 mexico_noticias.py &
python3 gaming_noticias.py &
wait  # → timeouts, deadlocks, "database is locked"

# ✅ Uno a la vez — predecible, debuggeable
python3 mexico_noticias.py
python3 gaming_noticias.py
```

---

## 2. Separa fetch de send

```
❌ scrape → generar resumen → enviar WA (un solo proceso)
   Un fallo en el medio lo pierde todo

✅ fetch → DB → send
              ↑
         audit trail, re-enviable, consultable
```

---

## 3. Agrupa los reinicios

```
Restart #1: gateway inicia, adquiere lock libsignal
Restart #2: gateway inicia, ve lock → sesión corrupta

→ WhatsApp deja de funcionar hasta reconectar QR
```

**Regla:** todos los cambios de config → un solo restart.
Cooldown mínimo entre reinicios automatizados.

---

## 4. Watchdogs simples con cooldown

```bash
# evita reiniciar en loop si el problema persiste
if [ -f "$LOCKFILE" ]; then
    AGE=$(( $(date +%s) - $(cat $LOCKFILE) ))
    [ $AGE -lt 600 ] && exit 0   # cooldown 10 min
fi

if ! openclaw channels ping --channel whatsapp; then
    date +%s > "$LOCKFILE"
    systemctl --user restart openclaw-gateway
fi
```

---

## 5. Modelo correcto para cada tarea

| Tarea | Modelo | Por qué NO el grande |
|-------|--------|---------------------|
| Clasificar tipo de bloqueador | `qwen2.5vl:3b` | 2-3s vs 3-5 min |
| Resumir 20 titulares | `gemma4:e4b` | Suficiente capacidad |
| Razonamiento multi-paso | `qwen3.5:9b` | Contexto y tool use |
| Análisis de deck TCG | `gemma4:26b` | Precisión necesaria |

---

## 6. El prompt es código

- Vive en archivos, no hardcodeado en el script
- **Especificidad** > generalidad
- `num_predict` importa — los modelos de razonamiento piensan antes de responder
- Prueba con **inputs reales**, no solo ejemplos perfectos

---

## 7. Logs estructurados desde el principio

```python
def log(event: str, **kwargs):
    print(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "event": event, **kwargs
    }), file=sys.stderr)

log("fetch_complete", source="mexico", items=23, duration_s=45.2)
log("article_blocked", url=url, reason="captcha")
```

Filtrable con `jq`, importable a Postgres, conectable a cualquier sistema de observabilidad.

---

## 8. La DB como tablero de control del agente

```
news_items.synced_at = NULL       → pendiente de sync
news_items.block_reason = NULL    → pendiente de scraping
news_items.block_reason = 'paywall'   → skip permanente
news_items.block_reason = 'extract_failed' → reintentar
news_items.content IS NOT NULL    → extraído exitosamente
```

Estado de cualquier ítem = un SELECT. Retry = un UPDATE.

---

## 9. Diseña para el fallo parcial

```
Ollama caído → fetch falla → filas sin resumen
    → send de esa fuente no tiene qué enviar
    → agente continúa con las otras fuentes
    → Ollama vuelve → próximo fetch completa el resumen
```

**Componentes independientes + estado en DB = resiliencia natural**

---

## 10. Observabilidad directa del homelab

```bash
# Estado del agente
systemctl --user status openclaw-gateway

# ¿Qué modelo está corriendo ahora mismo?
curl http://192.168.50.113:11434/api/ps

# ¿Qué artículos no tienen contenido?
sqlite3 ~/.openclaw/tools.db \\
  "SELECT source, count(*) FROM news_items \\
   WHERE content IS NULL GROUP BY source"

# ¿Qué pestaña tiene Chromium?
curl http://localhost:18800/json
```
"""

# ──────────────────────────────────────────────
# DECK 07 — Skills, tools y agentes
# ──────────────────────────────────────────────
DECKS["07-skills-tools-agentes"] = MARP_HEADER + """
<!-- class: title -->
# Skills, tools y agentes
## Un mapa completo de OpenClaw

---

## Los tres conceptos

```
AGENTE
└── decide qué hacer, mantiene contexto, usa LLM
    │
    usa SKILL
    └── módulo especializado: instrucciones + tools + identidad
        │
        invoca TOOL
        └── función ejecutable: script Python, API call, shell command
```

- **Tool** = un verbo. Algo que se puede *hacer*.
- **Skill** = un rol. *Quién eres* cuando haces ese trabajo.
- **Agente** = el actor. Decide *cuándo usar qué*.

---

## Los 6 skills en producción

| Skill | Dominio | LLM | Interactividad |
|-------|---------|-----|----------------|
| `mexico-noticias` | Noticias MX | gemma4:26b | Solo reporte |
| `intl-noticias` | Noticias mundo | gemma4:e4b | Solo reporte |
| `maker-noticias` | Maker/hardware | gemma4:e4b | Solo reporte |
| `cdmx-tcg-events` | Eventos TCG | qwen3.5:9b | Alta — filtros, lookup, fix |
| `pokemon-dia` | Info Pokémon | ninguno | Media — por nombre/# |
| `tcg-deck-analyst` | Meta competitivo | qwen3.5:9b | Solo reporte |

---

## Separación clara en el mismo dominio

```yaml
# tcg-deck-analyst
description: "ONLY for deck meta analysis: top decks,
  what's winning, deck rankings.
  NOT for: finding events, schedules, store locations"

# cdmx-tcg-events
description: "Use for ANY question about Pokémon TCG
  in CDMX: events, tournaments, challenges, locations.
  NOT for: deck meta, top decks, what decks are winning"
```

El router distingue ambos skills por su descripción semántica.
Sin separación explícita del "NOT for", el router se confunde.

---

## LLM como worker vs. orquestador

```
Worker (genera el output final):
  mexico-noticias, intl-noticias, maker-noticias
  → LLM recibe titulares → produce el resumen
  → el texto del modelo ES la respuesta

Orquestador (decide qué ejecutar, pasa el output):
  cdmx-tcg-events, tcg-deck-analyst, pokemon-dia
  → LLM elige el comando correcto
  → el script ES la fuente de verdad
  → regla: "devuelve el stdout completo, sin texto adicional"
```

---

## Aprendizaje activo sin reentrenamiento

```bash
# El usuario dice: "el mapa de Thunder Empire está mal"

cdmx_events_combined.py venues fix \\
  "Thunder Empire" \\
  "https://maps.app.goo.gl/correcto"

# → persiste en venue_overrides.json
# → los fetches futuros respetan el override
# → sin tocar el modelo, sin fine-tuning
```

> El estado externo (archivos, DB) como memoria del agente.

---

## Modo reactivo vs. proactivo

```
REACTIVO (pull) — el usuario dispara
  Usuario → Gateway → Router → Skill → Respuesta

PROACTIVO (push) — el reloj dispara
  7am: noticias-fetch-all.sh   (scraping + LLM)
  8am: noticias-send-all.sh   (envía a grupos WA)
  5pm: noticias-fetch-all.sh
  6pm: noticias-send-all.sh
```

Los crons son agentes sin interfaz conversacional.
El trigger es temporal, no conversacional.
"""

# ──────────────────────────────────────────────
# DECK 08 — Unraid
# ──────────────────────────────────────────────
DECKS["08-unraid"] = MARP_HEADER + """
<!-- class: title -->
# Unraid
## El sistema operativo para tu homelab de LLMs

---

## Qué es Unraid

```
┌─────────────────────────────────────────────┐
│  UNRAID SERVER                              │
│                                             │
│  ┌───────────┐  ┌──────────────┐  ┌──────┐ │
│  │  Array de │  │    Docker    │  │ VMs  │ │
│  │  discos   │  │  containers  │  │ KVM  │ │
│  │ (paridad) │  │   (con GUI)  │  │      │ │
│  └───────────┘  └──────────────┘  └──────┘ │
│                                             │
│  WebUI en http://tower.local                │
└─────────────────────────────────────────────┘
```

La intersección de NAS + hypervisor + Docker host.
Optimizado para homelabs, no para producción empresarial.

---

## Almacenamiento: mezcla discos de cualquier tamaño

```
RAID 5 tradicional:
  4 × 4TB = 12TB (mismo tamaño obligatorio)

Unraid Array:
  1 × 4TB (paridad)   ← solo necesitas 1 disco de paridad
  1 × 4TB + 1 × 3TB + 1 × 2TB + 1 × 1TB
  = 10TB usables con lo que ya tienes
```

Si falla un disco → solo pierdes los datos de ese disco.
Los demás siguen accesibles mientras reconstruyes.

---

## Docker con GUI: servicios para LLMs

| Servicio | Imagen | Para qué |
|----------|--------|----------|
| **Ollama** | `ollama/ollama` | LLM backend con GPU passthrough |
| **Open WebUI** | `open-webui/open-webui` | Interfaz web para Ollama |
| **Postgres** | `postgres:18` | Replica analítica |
| **Metabase** | `metabase/metabase` | Dashboards de datos del agente |
| **Uptime Kuma** | `louislam/uptime-kuma` | Monitoreo de servicios |

Community Apps = instalar cualquiera de estos con 1 clic.

---

## GPU passthrough: Ollama con VRAM dedicada

```
Unraid Host (sin GPU directa)
    │
    ├── VM: Windows (GPU 1 — para juegos/trabajo)
    └── Docker: Ollama (GPU 2 — para LLMs)
                Extra Parameters: --gpus all
```

Ollama tiene acceso **directo** a la VRAM sin overhead de virtualización.
Puedes dedicar una GPU entera al servidor LLM mientras otra
alimenta un escritorio Windows en la misma máquina.

---

## Cache pool: datos calientes vs. fríos

```
Cache Pool (NVMe SSDs — rápido, sin paridad)
  └── /mnt/cache/appdata/
      ├── ollama/      ← modelos que usas frecuente
      ├── postgres/    ← escrituras de DB
      └── open-webui/

Array de discos (HDDs + paridad — redundante, lento)
  └── /mnt/user/media/
      └── ollama/models/  ← modelos que rara vez usas
```

Unraid puede mover archivos entre cache y array automáticamente.

---

## Nuestra setup actual → con Unraid

```
HOY:                         CON UNRAID:
────────────────────         ────────────────────────
Ollama: proceso systemd  →   Contenedor Docker + GPU passthrough
Postgres: docker manual  →   Contenedor con volumen en array
Sin gestión de discos    →   Array con paridad automática
Backups: ninguno         →   Plugin de backup + rsync
Monitoreo: SSH + comandos→   Dashboard web
```

---

## ¿Vale la pena si ya tienes algo funcionando?

**Sí, si:**
- Pasas tiempo significativo manteniendo la infra vs. usándola
- Quieres mostrar el homelab a otros (la UI es muy accesible)
- Tienes varios discos de distinto tamaño sin protección de paridad
- Quieres VM + Docker + almacenamiento en una sola máquina

**No urgente si:**
- Tu setup funciona y eres el único usuario
- Solo tienes una máquina con un disco

**Limitaciones honestas:** licencia $69–$129 USD, curva de primera configuración (~1 fin de semana), no apto para SLAs de producción.
"""

# ──────────────────────────────────────────────
# Render con Marp CLI
# ──────────────────────────────────────────────
def write_and_render(slug: str, content: str):
    md_path = OUT / f"{slug}.md"
    html_path = OUT / f"{slug}.html"

    md_path.write_text(content, encoding="utf-8")

    result = subprocess.run(
        [
            "npx", "--yes", "@marp-team/marp-cli",
            str(md_path),
            "--output", str(html_path),
            "--html",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"  ✅  {html_path.name}")
    else:
        print(f"  ❌  {slug}")
        print(result.stderr[-500:])


def main():
    print(f"\nGenerando {len(DECKS)} slide decks en {OUT}/\n")
    for slug, content in DECKS.items():
        write_and_render(slug, content)
    print(f"\nListo. Abre los HTML en un navegador.")
    print(f"  → {OUT}/\n")


if __name__ == "__main__":
    main()
