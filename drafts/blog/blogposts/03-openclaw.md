# OpenClaw: el framework de agentes que conecta LLMs con el mundo real

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 3 de 6

---

Los LLMs son buenos generando texto. Los agentes son buenos *actuando*. La diferencia
entre un modelo que responde preguntas y un agente que toma decisiones y ejecuta acciones
es la capa de orquestación. **OpenClaw** es esa capa en nuestra setup.

---

## Qué es OpenClaw

OpenClaw es un framework de agentes conversacionales extensible via **skills** (habilidades).
Funciona como un proceso gateway que:

1. Escucha en un **canal de entrada** (WhatsApp, Telegram, HTTP, etc.)
2. Recibe un mensaje del usuario
3. Decide qué skill invocar (o usa el LLM directamente)
4. Ejecuta el skill y devuelve la respuesta al canal

Es conceptualmente similar a LangChain o AutoGen, pero con un foco distinto: está diseñado
para correr en un nodo único con canales de mensajería del mundo real, no para demos en
notebooks.

---

## Arquitectura de tres capas

```
┌─────────────────────────────────────────┐
│  Canal (WhatsApp / Telegram / HTTP)     │  ← entrada/salida del usuario
└─────────────────┬───────────────────────┘
                  │  mensajes
┌─────────────────▼───────────────────────┐
│  Gateway  (puerto 18789)                │
│  ├── Router: ¿qué skill usar?           │
│  ├── Context manager: historial         │
│  └── LLM fallback (qwen3.5:9b)          │  ← Ollama local
└─────────────────┬───────────────────────┘
                  │  invocación
┌─────────────────▼───────────────────────┐
│  Skills                                 │
│  ├── mexico-noticias                    │
│  ├── intl-noticias                      │
│  ├── maker-noticias                     │
│  ├── cdmx-tcg-events                    │
│  └── tcg-deck-analyst                   │
└─────────────────────────────────────────┘
```

---

## El gateway como proceso central

El gateway es el proceso que nunca para. Corre como servicio `systemd --user` y mantiene
conexiones persistentes con cada canal configurado. En WhatsApp, esto es especialmente
importante: la sesión de WhatsApp Web tiene un socket que puede desconectarse, y el
gateway es responsable de reconectarlo.

```bash
# Ver estado del gateway
systemctl --user status openclaw-gateway

# Logs en tiempo real
journalctl --user -u openclaw-gateway -f

# Reiniciar (por ejemplo, tras cambiar configuración)
systemctl --user restart openclaw-gateway
```

**Lección aprendida:** cada reinicio del gateway rompe y reconstituye la conexión con
WhatsApp, lo que puede provocar conflictos de sesión si hay múltiples reinicios en poco
tiempo. Agrupa tus cambios de configuración y reinicia una sola vez.

---

## Skills: la unidad de capacidad

Un skill es un módulo que extiende lo que el agente puede hacer. Cada skill tiene:

- Una **descripción** en lenguaje natural (el router la usa para decidir cuándo invocar el skill).
- Un **prompt de sistema** que configura el comportamiento del LLM para esa tarea.
- **Tools** (herramientas): funciones que el LLM puede invocar durante la conversación.
- Opcionalmente, **recursos** como archivos de datos o configuración.

```
~/.openclaw/workspace/skills/
├── mexico-noticias/
│   ├── skill.json          # descripción, modelo, configuración
│   └── tools/              # scripts invocables
├── cdmx-tcg-events/
│   ├── skill.json
│   └── venue_overrides.json # datos de configuración del skill
└── tcg-deck-analyst/
    └── skill.json
```

El skill `mexico-noticias`, por ejemplo, sabe cómo consultar la base de datos local
de noticias y formatear un resumen para WhatsApp. El LLM decide cómo presentar la
información; el skill define las herramientas con las que puede trabajar.

---

## Modelo del agente: tool use con Ollama

El corazón del agente es un LLM con **function calling** (o "tool use"). El modelo no
solo genera texto: puede decidir llamar a una función definida en el skill y usar su
resultado para continuar la conversación.

```
Usuario: "¿Qué noticias hay de tecnología hoy?"
         │
         ▼
LLM (qwen3.5:9b):
  → decide llamar tool: get_news(category="tech", date="today")
         │
         ▼
Tool ejecuta: SELECT * FROM news_items WHERE ...
         │
         ▼
LLM recibe resultados y genera respuesta en lenguaje natural
         │
         ▼
WhatsApp: "Hoy en tecnología: [resumen]"
```

Este patrón —LLM → tool → LLM— es el ciclo básico de un agente. Lo que hace interesante
a los multi-agente es cuando el resultado de un agente es la entrada de otro.

---

## WhatsApp como canal de producción

Usar WhatsApp como interfaz tiene ventajas no obvias para un sistema de agentes:

- **Fricción cero para el usuario**: no hay app que instalar, no hay login, no hay URL que recordar.
- **Notificaciones nativas**: el agente puede enviar proactivamente (no solo responder).
- **Grupos**: puedes tener múltiples "suscripciones" por grupo con audiencias distintas.
- **Multimedia**: el agente puede enviar imágenes, documentos, audios.

El tradeoff es que WhatsApp Web no es una API oficial, lo que introduce fragilidad
(actualizaciones de WhatsApp pueden romper la sesión). Por eso tenemos un watchdog.

```bash
# whatsapp-watchdog.sh — se ejecuta cada 5 minutos via cron
# Si el canal no responde, reinicia el gateway
if ! openclaw channels ping --channel whatsapp; then
    systemctl --user restart openclaw-gateway
fi
```

---

## Grupos WhatsApp: una suscripción por audiencia

Cada grupo de WhatsApp tiene su propio JID (identificador) y recibe contenido específico:

| Grupo | Contenido |
|-------|-----------|
| Auto Resúmenes | Noticias México + Internacional |
| make: read | Noticias maker/hacker/Arduino |
| gaming & tech | Noticias videojuegos |
| Eventos TCG | Eventos Pokémon TCG CDMX |

Esto es multi-agente en la dimensión de *distribución*: el mismo pipeline de datos
alimenta múltiples canales con formatos y audiencias distintas.

---

## El LLM local como backbone

Todos los skills usan `openai/ollama:qwen3:0.6b` (o modelos más grandes según la tarea)
como backend por defecto. La configuración está en `~/.openclaw/openclaw.json`:

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

OpenClaw usa la API compatible con OpenAI de Ollama (`/v1`), lo que significa que
**cualquier framework que soporte OpenAI SDK funciona con Ollama sin cambios** —
solo cambias la `baseURL` y el nombre del modelo.

---

*Siguiente: [Agentes de noticias: del RSS al resumen con LLM →](04-agentes-noticias.md)*
