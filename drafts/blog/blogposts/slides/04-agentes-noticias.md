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
