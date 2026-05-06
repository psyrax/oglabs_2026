# La infraestructura: hardware, servicios y topología

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 2 de 6

---

Antes de hablar de agentes necesitamos entender la capa en la que corren. Una arquitectura
mal pensada en infraestructura hace que los agentes fallen de maneras misteriosas: timeouts
aleatorios, estados inconsistentes, procesos huérfanos. Este post describe nuestra topología
y las decisiones detrás de cada componente.

---

## Visión general

```
┌──────────────────────────────────────────────────────────────┐
│  Raspberry Pi 5  (arm64, linux)                              │
│                                                              │
│  ┌─────────────────┐   ┌──────────────────────────────────┐ │
│  │  OpenClaw       │   │  Chromium (CDP :18800)           │ │
│  │  Gateway        │   │  Xvfb :0  (display virtual)      │ │
│  │  :18789         │   └──────────────────────────────────┘ │
│  │  (systemd user) │                                        │
│  └────────┬────────┘   ┌──────────────────────────────────┐ │
│           │            │  Cron jobs                        │ │
│           │            │  noticias-fetch 7am/17pm          │ │
│           │            │  noticias-send  8am/18pm          │ │
│           │            └──────────────────────────────────┘ │
│                                                              │
│  SQLite: ~/.openclaw/tools.db                                │
└──────────────────────┬───────────────────────────────────────┘
                       │  LAN  192.168.50.0/24
                       │
         ┌─────────────┴──────────────────┐
         │  Servidor LLM  (x86, 8GB VRAM) │
         │                                │
         │  Ollama  :11434                │
         │  ├── qwen3.5:9b  (agente)      │
         │  ├── gemma4:e4b  (resúmenes)   │
         │  ├── qwen2.5vl:3b (visión)     │
         │  └── gemma4:26b  (razonamiento)│
         │                                │
         │  Postgres 18  :5432 (Docker)   │
         │  DB: openclaw                  │
         └────────────────────────────────┘
```

---

## Componentes clave

### Raspberry Pi 5 — el orquestador

El Pi es el cerebro coordinador. No hace inferencia: su trabajo es orquestar, programar,
recibir mensajes y disparar acciones. Esto es importante: **separar el plano de control
del plano de cómputo** es lo que hace el sistema escalable.

Lo que corre en el Pi:

- **OpenClaw gateway** como servicio `systemd --user`. Un proceso persistente que:
  - Mantiene la conexión con WhatsApp.
  - Recibe mensajes y los enruta al skill correcto.
  - Gestiona contexto de conversación por usuario/grupo.
- **Chromium con CDP** para scraping de sitios JavaScript-heavy. El proceso tiene su propio
  perfil y escucha en el puerto 18800.
- **Xvfb** como display virtual (`:0`). Chromium necesita un display aunque sea headless real;
  el modo `--headless=new` tiene limitaciones con ciertos sitios anti-bot.
- **Scripts Python** en `~/scripts/tools/` — los "skills" de scraping que el agente invoca.
- **Cron jobs** que coordinan fetch y send en slots horarios.

### Servidor LLM — el motor de inferencia

Una máquina más potente (x86, GPU dedicada) corre **Ollama**. Los modelos disponibles
cubren diferentes necesidades:

| Modelo | Uso | Velocidad | VRAM |
|--------|-----|-----------|------|
| `qwen3.5:9b` | Agente general, razonamiento | Media | ~6GB |
| `gemma4:e4b` | Resúmenes de noticias | Rápida | ~4GB |
| `qwen2.5vl:3b` | Visión (screenshots) | Rápida | ~3GB |
| `gemma4:26b` | Razonamiento complejo | Lenta | ~16GB |

La separación del modelo por tarea es clave: usar un modelo de 26B para clasificar
si un elemento del DOM es un cookie banner es un desperdicio de recursos.

### Postgres 18 — la replica analítica

Postgres corre en Docker en el mismo servidor que Ollama. Su rol no es ser la fuente
de verdad (eso es SQLite local) sino ser la **replica analítica**: consultable con SQL
estándar, desde cualquier cliente de BI, con índices apropiados.

---

## Por qué SQLite como fuente de verdad

La elección de SQLite como base primaria sorprende a muchos. Las razones:

1. **Cero latencia de red** — el proceso que escribe está en la misma máquina que el archivo.
2. **Sin servidor que mantener** — nada se "cae", no hay conexiones que gestionar.
3. **Backups triviales** — `cp tools.db tools.db.bak` es tu backup.
4. **Suficiente para un nodo** — SQLite maneja perfectamente miles de escrituras/día en un solo proceso.

El tradeoff: SQLite no es consultable remotamente, no tiene tipos ricos, y escala mal bajo
escritura concurrente. Para eso existe la replica Postgres: consultas analíticas, dashboards,
joins complejos.

---

## Comunicación entre capas

Todos los componentes se comunican por **HTTP sobre LAN**:

- Pi → Ollama: `http://192.168.50.113:11434` (API REST de Ollama)
- Pi → Postgres: TCP `192.168.50.113:5432`
- Chromium → Pi (CDP): `ws://localhost:18800` (WebSocket local)

Esto tiene una ventaja enorme para debugging: puedes interceptar cualquier llamada con
`curl`, `psql` o las DevTools de Chrome y ver exactamente qué está pasando.

---

## Systemd como supervisor de procesos

En lugar de `screen`, `tmux` o `nohup`, usamos `systemd --user` para los procesos
persistentes. Ventajas:

```ini
# ~/.config/systemd/user/openclaw-gateway.service
[Unit]
Description=OpenClaw Agent Gateway
After=network.target

[Service]
ExecStart=/home/psyrax/.npm-global/bin/openclaw gateway start
Restart=on-failure
RestartSec=5s
Environment=HOME=/home/psyrax

[Install]
WantedBy=default.target
```

- `Restart=on-failure` — si el gateway crashea, vuelve solo en 5 segundos.
- Los logs van a `journalctl --user -u openclaw-gateway` — consultables con filtros de tiempo.
- `systemctl --user enable` hace que arranque en cada boot sin intervención.

---

## Anti-patrón aprendido: no ejecutar en paralelo

La tentación inicial fue paralelizar todo: 7 scrapers corriendo simultáneamente, llamadas
a Ollama en paralelo. El resultado fue:

- Ollama bloqueándose (solo puede atender una inferencia a la vez con los modelos grandes).
- Chromium abriendo 7 pestañas al mismo tiempo, saturando la RAM del Pi.
- Race conditions en SQLite con múltiples escritores.

La solución: **todo secuencial, con orquestación explícita**. Un script maestro llama
a cada componente en orden y espera a que termine antes de pasar al siguiente.
El rendimiento total es similar (el cuello de botella es Ollama, no la concurrencia
del orquestador) y la depuración es trivial.

---

*Siguiente: [OpenClaw: el framework de agentes →](03-openclaw.md)*
