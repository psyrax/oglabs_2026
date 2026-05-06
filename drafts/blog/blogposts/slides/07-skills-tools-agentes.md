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

cdmx_events_combined.py venues fix \
  "Thunder Empire" \
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
