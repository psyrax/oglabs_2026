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
