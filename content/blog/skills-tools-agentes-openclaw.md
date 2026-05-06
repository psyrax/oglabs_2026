Title: Skills, tools y agentes en OpenClaw: un mapa completo
Date: 2026-05-05
Category: blog
Slug: skills-tools-agentes-openclaw

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 5 de 8

---

Una de las preguntas más frecuentes cuando presentamos este sistema es: *¿cuál es la diferencia
entre un skill, un tool y un agente?* Los tres términos se usan en la literatura de LLMs pero
con significados que varían por framework. Este post explica cómo funcionan en OpenClaw con
ejemplos concretos de lo que tenemos en producción.

---

## Los tres conceptos

```
┌─────────────────────────────────────────────────────────┐
│  AGENTE                                                 │
│  LLM con memoria, contexto de conversación,             │
│  capacidad de decidir qué hacer y cómo responder        │
│                                                         │
│    usa                                                  │
│    ┌──────────────────────────────────────────────┐    │
│    │  SKILL                                       │    │
│    │  Módulo especializado con instrucciones,     │    │
│    │  personalidad y acceso a herramientas        │    │
│    │  específicas para un dominio                 │    │
│    │                                              │    │
│    │    invoca                                    │    │
│    │    ┌────────────────────────────────────┐   │    │
│    │    │  TOOL                              │   │    │
│    │    │  Función ejecutable: script        │   │    │
│    │    │  Python, comando shell, API call   │   │    │
│    │    └────────────────────────────────────┘   │    │
│    └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

En términos simples:
- **Tool** = un verbo. Algo que se puede *hacer*.
- **Skill** = un rol. La configuración de *quién eres* cuando haces ese trabajo.
- **Agente** = el actor. El LLM que decide *cuándo usar qué* y *cómo presentar el resultado*.

---

## Los 6 skills en producción

Cada skill vive en `~/.openclaw/workspace/skills/<nombre>/SKILL.md` y define:
- Cuándo activarse (descripción semántica para el router)
- Qué comandos ejecutar y cómo
- Reglas de formato de respuesta
- Qué NO hacer

---

### `mexico-noticias` — Noticias de México

**Propósito:** Resumen imparcial del día combinando 6 medios mexicanos con distintas
líneas editoriales.

**Fuentes:**
| Medio | Línea editorial |
|-------|----------------|
| Animal Político | Independiente |
| La Jornada | Izquierda |
| El Universal | Centro |
| Milenio | Centro |
| El Financiero | Centro-derecha |
| Proceso | Independiente |

**Cómo funciona:** El skill invoca `mexico_noticias.py report`, que hace scraping CDP de
cada sitio (son todos JavaScript-heavy), agrega los titulares, y los pasa a `gemma4:26b`
para generar el resumen. El modelo más grande (26B) aquí no es accidental: la tarea requiere
síntesis de múltiples perspectivas editoriales con criterio.

**Triggers:** `"noticias"`, `"qué pasó hoy"`, `"resumen del día"`, `"qué está pasando"`

**Caché:** 2 horas (ventanas de reloj par)

---

### `intl-noticias` — Noticias internacionales

**Propósito:** Perspectiva global con representación geográfica balanceada. El diseño
intencional con medios de distintas regiones reduce el sesgo de una sola visión del mundo.

**Fuentes:**
| Medio | Región / perspectiva |
|-------|---------------------|
| Reuters | Global, neutral |
| BBC | UK, centro |
| Al Jazeera | Sur global, Qatar |
| DW / Deutsche Welle | Alemania, centro |
| France 24 | Francia, centro |
| The Guardian | UK, centro-izquierda |
| AP News | Global, neutral |
| El País English | España, centro |

**Cómo funciona:** Similar a `mexico-noticias` pero con CDP en perfiles separados
(`"intl"`) para mantener cookies de cada sitio aisladas. Usa `gemma4:e4b` (más rápido,
suficiente para este nivel de síntesis).

**Triggers:** `"noticias internacionales"`, `"qué pasa en el mundo"`, `"world news"`

---

### `maker-noticias` — Noticias maker, hardware y hacking

**Propósito:** Feed curado para la comunidad maker: proyectos de hardware, hacks,
nuevos microcontroladores, tutoriales de electrónica.

**Fuentes:**
| Medio | Especialidad |
|-------|-------------|
| Hackaday | Hacks y proyectos de ingeniería |
| Hackster.io | Proyectos maker de comunidad |
| Make Magazine | DIY y maker culture |
| Adafruit Blog | Electrónica y componentes |
| Arduino Blog | Arduino y sistemas embebidos |
| Tom's Hardware | Hardware de PC y chips |

**Diferencia técnica clave:** Este skill usa RSS en lugar de CDP. Los sitios de comunidad
maker publican feeds RSS bien mantenidos con contenido completo. Adafruit en particular
incluye el artículo completo en `<content:encoded>`, lo que evita el scraping del sitio
(que usa Cloudflare).

**Caché:** 4 horas

---

### `cdmx-tcg-events` — Eventos Pokémon TCG en CDMX

**Propósito:** El skill más interactivo: no solo reporta, también responde preguntas
específicas sobre tiendas, fechas, tipos de torneo y puede corregir datos manualmente.

**Fuentes de datos:**
| Fuente | Método | Información |
|--------|--------|-------------|
| `pokemon.com` | CDP (browser automation) | Torneos premier, dirección exacta, hora |
| `pokedata.ovh` | HTTP API REST | Ligas, amistosos, cobertura más amplia |

**Comandos que el agente puede invocar:**

```bash
# Semana completa
cdmx_events_combined.py report

# Filtros
cdmx_events_combined.py report --hoy
cdmx_events_combined.py report --fecha 2026-05-10
cdmx_events_combined.py report --type challenge   # solo torneos serios

# Info de una tienda
cdmx_events_combined.py lookup "tao games"

# Corregir mapa erróneo (override persistente)
cdmx_events_combined.py venues fix "Thunder Empire" "https://maps.app.goo.gl/..."
```

**Lo que lo hace especial:** El agente puede *corregir datos* via `venues fix`. Cuando
un usuario dice "el mapa de Thunder Empire está mal", el skill ejecuta el override y
persiste el cambio en `venue_overrides.json`. Los fetches futuros respetan el override.
Esto es un patrón de **aprendizaje activo via feedback del usuario** sin reentrenamiento.

**Triggers:** `"eventos en CDMX"`, `"torneos esta semana"`, `"dónde queda [tienda]"`,
`"hay cups pronto"`, `"eventos del sábado"`

---

### `pokemon-dia` — Pokémon del día

**Propósito:** El skill más liviano y el más querido por los usuarios. Envía la imagen
oficial de un Pokémon junto con su tipo, número y entrada de Pokédex.

**Cómo funciona:** Llama a `pokemon-dia-skill.sh`, que consulta `PokeAPI` para obtener
datos y la imagen oficial, luego usa la función de envío de imágenes de OpenClaw para
mandarla directamente al chat. El skill rastrilla en la DB los Pokémon ya mostrados
para no repetir.

**Modos:**
```bash
# Random (sin repetir los ya vistos)
pokemon-dia-skill.sh random

# Pokémon específico
pokemon-dia-skill.sh get pikachu
pokemon-dia-skill.sh get 006   # por número
```

**Nota arquitectónica importante:** La respuesta del agente en este skill es *solo* el
output del script (`✅`). El script es el que envía el mensaje con imagen — no el LLM.
Este es un patrón donde el tool hace el trabajo real y el LLM solo orquesta.

**Triggers:** `"pokémon del día"`, `"sorpréndeme"`, `"háblame de Charizard"`, cualquier
nombre de Pokémon solo

---

### `tcg-deck-analyst` — Meta de Pokémon TCG

**Propósito:** Análisis del meta competitivo global: top 10 decks del formato Standard
y City Leagues de Japón en los últimos 30 días.

**Fuentes de datos:**
| Fuente | Método | Datos |
|--------|--------|-------|
| `play.limitlesstcg.com` | API REST | Torneos Standard, decklists |
| `limitlesstcg.com` | Scraping | City League JP |

**Diferencia con `cdmx-tcg-events`:** Este skill responde *qué decks ganan*, el otro
responde *dónde jugar*. La descripción semántica de cada skill define explícitamente
a quién *no* debe enrutar:

```yaml
# tcg-deck-analyst
description: "ONLY for deck meta analysis: top decks, what's winning...
  NOT for: finding events, schedules, tournaments to attend"

# cdmx-tcg-events
description: "Use for ANY question about Pokémon TCG in CDMX: events, tournaments...
  NOT for: deck meta, top decks, or what decks are winning"
```

Esta separación explícita en las descripciones es lo que permite al router del agente
hacer la distinción correcta entre dos skills del mismo dominio (Pokémon TCG).

**Triggers:** `"meta"`, `"top decks"`, `"qué decks ganan"`, `"reporte de meta"`

---

## El mapa completo: un usuario, seis especialistas

```
                    Usuario: "¿qué pasa en México?"
                                    │
                            Gateway (router)
                                    │
                    analiza descripción semántica de skills
                                    │
                    ┌───────────────▼──────────────┐
                    │        mexico-noticias        │
                    │                               │
                    │  exec: mexico_noticias.py     │
                    │   → CDP scraping (6 fuentes)  │
                    │   → Ollama gemma4:26b          │
                    │   → resumen con URLs           │
                    └───────────────────────────────┘

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    Usuario: "hay torneos este sábado?"
                                    │
                            Gateway (router)
                                    │
                    ┌───────────────▼──────────────┐
                    │       cdmx-tcg-events         │
                    │                               │
                    │  exec: cdmx_events_combined   │
                    │   → DB cache o CDP fetch      │
                    │   → pokedata.ovh API           │
                    │   → reporte agrupado por día  │
                    └───────────────────────────────┘

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    Usuario: "qué decks están ganando?"
                                    │
                            Gateway (router)
                                    │
                    ┌───────────────▼──────────────┐
                    │       tcg-deck-analyst        │
                    │                               │
                    │  exec: tcg-tournament-report  │
                    │   → limitlesstcg API           │
                    │   → City League JP scraping   │
                    │   → top 10 con porcentajes    │
                    └───────────────────────────────┘
```

---

## Tabla comparativa de los 6 skills

| Skill | Dominio | Fuente de datos | Método fetch | LLM usado | Interactividad |
|-------|---------|----------------|--------------|-----------|----------------|
| `mexico-noticias` | Noticias MX | 6 medios web | CDP (JS) | gemma4:26b | Solo reporte |
| `intl-noticias` | Noticias intl | 8 medios web | CDP (JS) | gemma4:e4b | Solo reporte |
| `maker-noticias` | Maker/hardware | 6 blogs | RSS | gemma4:e4b | Solo reporte |
| `cdmx-tcg-events` | Eventos TCG | pokemon.com + API | CDP + HTTP | router (qwen3.5) | Alta — filtros, lookup, fix |
| `pokemon-dia` | Info Pokémon | PokeAPI | HTTP REST | ninguno | Media — por nombre/número |
| `tcg-deck-analyst` | Meta competitivo | limitlesstcg | HTTP + scraping | router (qwen3.5) | Solo reporte |

---

## Cuándo el LLM es el worker vs. cuándo es el orquestador

Esta distinción es una de las más importantes del diseño:

**LLM como worker** (genera el output final):
- `mexico-noticias`, `intl-noticias`, `maker-noticias`: el LLM recibe los titulares
  y produce el resumen. El output del agente *es* la generación del modelo.

**LLM como orquestador** (decide qué ejecutar, pasa el output):
- `cdmx-tcg-events`, `tcg-deck-analyst`, `pokemon-dia`: el LLM decide qué comando
  correr y en qué formato presentar el resultado. El output viene del script, no del modelo.

La regla crítica en todos los skills de reporte es:
> *"Devuelve el stdout completo. Sin texto adicional."*

Esto evita que el LLM "mejore" creativamente el output del script con información
que no está en los datos (alucinación). Cuando el script es la fuente de verdad,
el LLM es un passthrough.

---

## La capa de tools: los scripts Python

Debajo de los skills hay 10+ scripts Python en `~/scripts/tools/`. Estos son los
"tools" que el agente puede invocar — funciones ejecutables que hacen el trabajo real:

| Script | Qué hace | Método principal |
|--------|----------|-----------------|
| `mexico_noticias.py` | Scraping + resumen noticias MX | CDP, Ollama |
| `intl_noticias.py` | Scraping + resumen noticias intl | CDP, Ollama |
| `maker_noticias.py` | Scraping + resumen maker | RSS, Ollama |
| `gaming_noticias.py` | Scraping + resumen gaming | RSS, Ollama |
| `cdmx_events_combined.py` | Eventos TCG CDMX (combinado) | CDP + HTTP API |
| `pokemon_events_browser.py` | Scraper pokemon.com | CDP |
| `cdmx_events.py` | Scraper pokedata.ovh | HTTP API |
| `pokemon_dia.py` | Info y foto de Pokémon | PokeAPI HTTP |
| `tcg-tournament-report-print.py` | Meta TCG report | limitlesstcg API |
| `sync_all_to_pg.py` | Sync SQLite → Postgres | psycopg2 |
| `db.py` | Utilidades SQLite compartidas | sqlite3 |

Cada script tiene un CLI con subcomandos estándar: `fetch`, `report`, `headlines`.
Esto permite llamarlos tanto desde el agente (via `exec`) como desde cron directamente,
sin cambiar el código.

---

## Los crons como agentes sin conversación

Una pieza que a veces se pasa por alto: **los crons son agentes también**, pero sin
interfaz conversacional. Son pipelines que corren automáticamente en horarios fijos:

```
7:00 AM  → noticias-fetch-all.sh    (fetcha las 4 fuentes)
8:00 AM  → noticias-send-all.sh     (envía todo + fetch articles + sync PG)
5:00 PM  → noticias-fetch-all.sh    (segundo ciclo)
6:00 PM  → noticias-send-all.sh
```

La diferencia con un skill interactivo:
- No hay usuario que dispare la acción — el reloj es el trigger
- No hay LLM decidiendo qué hacer — el script sabe exactamente qué ejecutar
- El "output" no es una respuesta en chat — son mensajes enviados proactivamente
  a grupos de WhatsApp

Esto es el patrón **push** vs. el patrón **pull** de los skills interactivos.

---

## Resumen del ecosistema completo

```
┌─────────────────────────────────────────────────────────────────┐
│  MODO REACTIVO (pull) — responde cuando el usuario pregunta     │
│                                                                 │
│  Usuario → Gateway → Router → Skill → Tool(s) → Respuesta      │
│                                                                 │
│  Skills: mexico-noticias, intl-noticias, maker-noticias,        │
│          cdmx-tcg-events, pokemon-dia, tcg-deck-analyst         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  MODO PROACTIVO (push) — envía sin que nadie lo pida            │
│                                                                 │
│  Cron → Script → Ollama (opcional) → WhatsApp group            │
│                                                                 │
│  Jobs: noticias-fetch-all, noticias-send-all,                   │
│        eventos TCG matutino, pokémon del día,                   │
│        sync Postgres                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  CAPA DE DATOS — estado compartido entre ambos modos            │
│                                                                 │
│  SQLite (local, fuente de verdad)                               │
│     ↓ sync incremental post-send                                │
│  Postgres (Docker, analítica y consultas BI)                    │
└─────────────────────────────────────────────────────────────────┘
```

La riqueza del sistema no está en ningún componente individual sino en la combinación:
skills especializados que saben exactamente qué hacer en su dominio, tools que encapsulan
la lógica de datos, y un agente central que sabe a quién preguntar.

---

*← [Lecciones aprendidas](06-lecciones.md) | [Inicio de la serie](00-indice.md)*
