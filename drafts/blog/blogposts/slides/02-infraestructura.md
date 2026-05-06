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
