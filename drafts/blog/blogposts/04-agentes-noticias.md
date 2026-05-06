# Agentes de noticias: del RSS al resumen con LLM

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 4 de 6

---

Este post describe uno de los pipelines más complejos de nuestra setup: agentes que
monitorean fuentes de noticias, hacen scraping de sitios JavaScript-heavy, lidian con
mecanismos anti-bot, y generan resúmenes concisos usando LLMs. Es un caso de estudio
real de multi-agente aplicado a data journalism automatizado.

---

## El pipeline completo

```
Fuentes RSS / Sitios web
         │
         ▼
┌────────────────────┐
│  Fetch  (7am/17pm) │  ← extrae headlines + URLs
│  ├── RSS parser    │
│  └── CDP scraper   │  ← Chromium headless
└────────┬───────────┘
         │  SQLite: news_items (URL, título, sin contenido)
         ▼
┌────────────────────┐
│  LLM Summary       │  ← Ollama gemma4:e4b
│  (dentro del fetch)│
└────────┬───────────┘
         │  SQLite: resumen generado
         ▼
┌────────────────────┐
│  Send  (8am/18pm)  │  ← openclaw send-all
│  → WhatsApp groups │
└────────┬───────────┘
         │  (post-send)
         ▼
┌────────────────────┐
│  Fetch Articles    │  ← scraping de cuerpos completos
│  (CDP + visión)    │  ← Ollama qwen2.5vl:3b para anti-bot
└────────┬───────────┘
         │  SQLite: news_items.content
         ▼
┌────────────────────┐
│  Sync → Postgres   │  ← push incremental
└────────────────────┘
```

---

## Cuatro agentes especializados

Cada dominio de noticias tiene su propio script Python con su lógica de scraping:

| Agente | Fuentes | Método |
|--------|---------|--------|
| `mexico_noticias.py` | El País MX, Reforma, El Universal, Milenio, Expansión, La Jornada | CDP (JavaScript-heavy) |
| `intl_noticias.py` | BBC, Reuters, NYT, The Guardian, Le Monde, DW, Al Jazeera, El País | CDP |
| `maker_noticias.py` | Hackaday, Hackster, Make, Adafruit, Arduino Blog, Tom's Hardware | RSS |
| `gaming_noticias.py` | Kotaku, Game Developer, Ars Technica, The Verge, RPS, Eurogamer | RSS |

La elección entre CDP y RSS no es arbitraria: los sitios de noticias tradicionales
suelen tener JavaScript que bloquea el scraping simple con `requests`. Los sitios
de la comunidad maker/gaming suelen tener feeds RSS bien mantenidos.

---

## CDP: Chromium como herramienta de scraping

El **Chrome DevTools Protocol (CDP)** permite controlar Chromium programáticamente
a nivel bajo: navegar URLs, ejecutar JavaScript, tomar screenshots, interceptar red.
A diferencia de Selenium o Playwright, CDP no requiere WebDriver y tiene latencia menor.

```python
# Patrón básico de navegación con CDP
async def navigate_and_extract(url: str) -> str:
    async with CDPSession(port=18800) as session:
        await session.navigate(url)
        await session.wait_for_load()
        content = await session.evaluate(ARTICLE_EXTRACT_JS)
        return content
```

El browser tiene un **perfil persistente** por agente (`news`, `intl`, `gaming-art`, etc.)
que mantiene cookies entre sesiones. Esto es crucial: muchos sitios muestran cookie banners
solo en la primera visita. Con el perfil persistente, el agente ya "aceptó" la política
de cookies y puede acceder al contenido directamente.

---

## El problema anti-bot y cómo lo resolvemos

El scraping moderno enfrenta varios tipos de bloqueos:

```
┌─────────────────┬──────────────────────────────────┬─────────────────┐
│ Tipo            │ Ejemplo                          │ Solución        │
├─────────────────┼──────────────────────────────────┼─────────────────┤
│ Cookie banner   │ "Acepta las cookies para entrar" │ Vision + dismiss│
│ Captcha         │ DataDome, reCAPTCHA               │ Cookies previas │
│ Paywall         │ "Suscríbete para leer"            │ Marcar y skip   │
│ Cloudflare      │ "Just a moment..."               │ RSS fallback    │
│ Login wall      │ "Inicia sesión para continuar"   │ Marcar y skip   │
└─────────────────┴──────────────────────────────────┴─────────────────┘
```

### Vision-assisted cookie dismiss

El caso más interesante es el cookie banner. Los textos de los botones varían:
"Acepto", "Accept All", "Aceptar todo", "Continuar sin aceptar". Un hardcode de textos
falla cuando un sitio cambia su banner. La solución: **usar un VLM** (modelo de visión).

```python
# lib/article_extractor.py — flujo de extracción con fallback visual
async def process_article(url: str, browser: CDPBrowser) -> str:
    content = await extract_text(url, browser)

    if len(content) < 100:
        # Poco contenido → puede haber un bloqueador visual
        screenshot = await browser.take_screenshot()

        classification = await visual_guide.classify(
            screenshot,
            prompt="¿Qué bloquea el contenido? cookie_wall | captcha | paywall | login_wall | none"
        )

        if classification.type == "cookie_wall":
            # El VLM también devuelve el texto exacto del botón
            await dismiss_cookie_banner(browser, button_text=classification.button_text)
            content = await extract_text(url, browser)  # segundo intento

        elif classification.type in ("captcha", "paywall", "login_wall"):
            # Bloqueo permanente — no reintentar
            await mark_blocked(url, reason=classification.type)
            return ""

    return content
```

El modelo de visión (`qwen2.5vl:3b`) tarda ~2-3 segundos por screenshot. Es lento
comparado con extracción de texto puro, pero se llama solo cuando la extracción normal
falla, no en cada artículo.

### RSS como fallback para Cloudflare

Adafruit Blog usa Cloudflare Challenge. El browser CDP no pasa la verificación de
JavaScript. La solución elegante: **el RSS de Adafruit incluye el contenido completo**
en `<content:encoded>`. Cuando el RSS tiene ≥500 caracteres de contenido, lo usamos
directamente y nunca tocamos el sitio con el browser.

```python
def parse_feed(url: str) -> list[NewsItem]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        content = entry.get("content", [{}])[0].get("value", "")
        # Si el RSS trae contenido rico, úsalo directo
        items.append(NewsItem(
            title=entry.title,
            url=entry.link,
            content=content if len(content) >= 500 else None
        ))
    return items
```

Este patrón —preferir la fuente más directa disponible— es generalizable: antes de
abrir un browser y pelear con anti-bot, pregunta si hay una API o feed que tenga
los datos que necesitas.

---

## El LLM como redactor: generación de resúmenes

Una vez que tenemos los titulares, los pasamos a `gemma4:e4b` para generar el resumen
del día. El prompt es crítico:

```
SISTEMA: Eres un editor de noticias conciso. Recibirás una lista de titulares
con sus URLs. Genera un resumen para WhatsApp usando EXACTAMENTE los titulares
tal como aparecen. No parafrasees ni inventes. Incluye la URL de cada ítem.

USUARIO: [lista de titulares con URLs]

ASISTENTE: [resumen formateado para WhatsApp]
```

Lección importante: en versiones anteriores el prompt decía "resume los temas principales"
y el modelo generaba paráfrasis genéricas. El cambio a "copia los titulares exactos"
mejoró dramáticamente la fidelidad del resumen.

El parámetro `num_predict=8000` es necesario para modelos de razonamiento como `gemma4:e4b`
que usan tokens internamente para el "chain of thought" antes de generar la respuesta visible.
Con `num_predict=3000`, el modelo se cortaba antes de terminar el resumen.

---

## Separación de fetch y send

Una decisión de arquitectura importante: **fetch y send son procesos separados** con
almacenamiento intermedio en SQLite.

- **Fetch (7am/17pm)**: extrae headlines, genera resumen, guarda en DB. No envía nada.
- **Send (8am/18pm)**: lee el resumen de DB y lo envía por WhatsApp.

Ventajas:
1. Si el send falla (WhatsApp down, gateway caído), el fetch ya está hecho. No re-scrapiamos.
2. Puedes re-enviar el resumen del día sin re-scraping: `SELECT` en DB y vuelve a mandar.
3. El fetch puede tardar 10-15 minutos (Ollama es lento). El send es casi instantáneo.
4. Tienes historial auditado de lo que se envió y cuándo.

```sql
-- Consultar resúmenes enviados hoy
SELECT source, summary, created_at 
FROM noticias_headlines 
WHERE date(created_at) = date('now')
ORDER BY created_at;
```

---

## Crons: la orquestación temporal

Los cuatro agentes están coordinados por dos pares de scripts:

```bash
# noticias-fetch-all.sh
python3 tools/mexico_noticias.py fetch
python3 tools/intl_noticias.py fetch
python3 tools/maker_noticias.py fetch
python3 tools/gaming_noticias.py fetch

# noticias-send-all.sh
bash eventos-hoy-send.sh          # solo AM
bash pokemon-dia.sh               # solo AM
bash noticias-mexico-send.sh
bash intl-noticias-send.sh
bash maker-noticias-send.sh
bash gaming-noticias-send.sh
bash noticias-fetch-articles-all.sh  # scraping de cuerpos, post-send
python3 tools/sync_all_to_pg.py      # sync a Postgres
```

El script detecta la hora para omitir contenido no aplica al turno de tarde:

```bash
HOUR=$(date +%H)
if [ "$HOUR" -lt 12 ]; then
    bash eventos-hoy-send.sh
    bash pokemon-dia.sh
fi
```

---

*Siguiente: [Persistencia y observabilidad: SQLite → Postgres →](05-persistencia.md)*
