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
