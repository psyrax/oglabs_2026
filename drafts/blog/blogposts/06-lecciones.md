# Lecciones aprendidas y patrones reusables

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 6 de 6

---

Después de meses construyendo y rompiendo este sistema, hay un conjunto de principios
que hemos destilado. No son obvios al principio, pero cada uno vino de una falla real.
Este post es el que desearíamos haber leído antes de empezar.

---

## 1. Secuencialidad sobre paralelismo (casi siempre)

El instinto de un data scientist es paralelizar: más hilos, más throughput. Con agentes
que comparten recursos de inferencia, esto es un error.

**El problema:**
- Ollama no puede atender dos inferencias grandes simultáneamente (el modelo entero
  cabe en VRAM una sola vez).
- Chromium con múltiples pestañas compite por RAM y CPU en el Pi.
- SQLite con múltiples escritores concurrentes genera errores `database is locked`.

**La solución:** un script maestro secuencial. Cada componente termina completamente
antes de que empiece el siguiente.

```bash
# MAL: 7 procesos compitiendo
python3 mexico_noticias.py &
python3 intl_noticias.py &
python3 gaming_noticias.py &
wait

# BIEN: uno a la vez
python3 mexico_noticias.py
python3 intl_noticias.py
python3 gaming_noticias.py
```

El tiempo total es similar (el cuello de botella es Ollama, no la orquestación).
La depuración es dramáticamente más fácil.

---

## 2. Separar fetch de send

Nunca hagas fetch-y-send en el mismo proceso si puedes evitarlo.

El fetch (scraping + LLM) puede tardar 10-30 minutos y puede fallar parcialmente.
El send (envío a WhatsApp) debe ser rápido y atómico. Si los mezclas:

- Un fallo en el scraping bloquea el send.
- Un fallo en el send desperdicia el scraping.
- No puedes re-enviar sin re-scrapear.

Con separación y almacenamiento intermedio en SQLite:

```
fetch → DB → send
         ↑
    audit trail
    re-enviable
    consultable
```

---

## 3. Los reintentos deben ser tolerantes al contexto

Un reintento ingenuo (`while failed: retry`) puede romper cosas en vez de arreglarlas.

**El caso real:** el gateway de WhatsApp usa `libsignal` para cifrado. El proceso
mantiene un lock de sesión. Si reinicias el gateway dos veces rápidamente, el segundo
inicio encuentra el lock de la sesión anterior y la sesión de WhatsApp se corrompe.

```
Restart #1: gateway inicia, adquiere lock
Restart #2: gateway inicia, ve lock, fuerza limpieza → sesión corrupta
```

**La lección:** agrupa todos los cambios de configuración que necesitas, luego reinicia
una sola vez. Si tu watchdog reinicia automáticamente, asegúrate de que tiene un cooldown
suficiente para que el proceso anterior termine completamente.

---

## 4. Watchdogs: simples y con idempotencia

Un watchdog efectivo tiene tres características:

1. **Verifica estado real**, no solo que el proceso exista.
2. **Tiene cooldown** para no reiniciar en loops.
3. **Es idempotente**: reiniciar algo que ya funciona no lo rompe.

```bash
# whatsapp-watchdog.sh — corre cada 5 min via cron
LOCKFILE=/tmp/wa-watchdog.lock

# Cooldown: no reiniciar si ya se reinició hace menos de 10 minutos
if [ -f "$LOCKFILE" ]; then
    LAST=$(cat "$LOCKFILE")
    NOW=$(date +%s)
    if [ $((NOW - LAST)) -lt 600 ]; then
        exit 0
    fi
fi

# Verificar estado real (responde ping, no solo que el proceso existe)
if ! openclaw channels ping --channel whatsapp 2>/dev/null; then
    echo "WhatsApp down — reiniciando gateway"
    date +%s > "$LOCKFILE"
    systemctl --user restart openclaw-gateway
fi
```

---

## 5. Modelos distintos para tareas distintas

No uses el modelo más grande para todo. Hay un tradeoff real:

| Tarea | Modelo recomendado | Justificación |
|-------|--------------------|---------------|
| Clasificar tipo de bloqueador (cookie/captcha/paywall) | `qwen2.5vl:3b` | Tarea simple, necesita velocidad |
| Resumir 20 titulares de noticias | `gemma4:e4b` | Buena capacidad de síntesis, rápido |
| Razonamiento multi-paso del agente | `qwen3.5:9b` | Contexto largo, tool use |
| Análisis complejo de deck TCG | `gemma4:26b` | Alta precisión, latencia aceptable |

Un modelo de 26B tarda 3-5 minutos en clasificar un cookie banner. Un modelo de 3B
tarda 2-3 segundos. La precisión en esa tarea específica es indistinguible.

---

## 6. El prompt es código: trátalo como tal

Cada cambio de prompt es un cambio de comportamiento del sistema. Los mismos principios
que aplicas a código aplican a prompts:

- **Control de versiones**: los prompts viven en archivos, no hardcodeados en el script.
- **Especificidad sobre generalidad**: "copia los titulares exactos con sus URLs" produce
  resultados más consistentes que "resume las noticias".
- **Prueba con inputs reales**: un prompt que funciona bien con un ejemplo puede fallar
  con input real que tiene caracteres especiales, longitudes distintas, o idiomas mixtos.
- **`num_predict` importa**: los modelos de razonamiento usan tokens para pensar antes
  de generar la respuesta. Con `num_predict` bajo, el modelo se corta en medio del
  razonamiento y produce output incompleto.

---

## 7. Logs estructurados desde el principio

Los logs de texto libre son ilegibles en producción. Desde el principio, estructura tus logs:

```python
import json
import sys

def log(event: str, **kwargs):
    print(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "event": event,
        **kwargs
    }), file=sys.stderr)

# Uso
log("fetch_complete", source="mexico", items=23, duration_s=45.2)
log("article_blocked", url=url, reason="captcha", attempts=1)
log("summary_generated", tokens=1847, model="gemma4:e4b", duration_s=12.1)
```

Con logs JSON puedes filtrar con `jq`, importar a Postgres, o conectar a cualquier
sistema de observabilidad después.

---

## 8. La DB como fuente de verdad del estado del agente

Cada acción importante que hace el agente debe quedar registrada en la DB. No solo
el output final: el estado intermedio también.

```
news_items.synced_at = NULL    → pendiente de sync a Postgres
news_items.block_reason = NULL → pendiente de scraping
news_items.block_reason = 'paywall' → bloqueo permanente (no reintentar)
news_items.block_reason = 'extract_failed' → error transitorio (sí reintentar)
news_items.content IS NOT NULL → contenido extraído exitosamente
```

Este esquema convierte la DB en un **tablero de control del agente**. Puedes saber
el estado de cada ítem con un SELECT. Puedes re-intentar items específicos con
un UPDATE. Puedes auditar qué pasó con cada URL.

---

## 9. Diseña para el fallo parcial

En un sistema de múltiples componentes, asumir que todo va a funcionar es un error.
El diseño debe partir de: "¿qué pasa si este componente falla?"

```
Ollama caído → el fetch falla → las filas quedan sin resumen →
el send de esa fuente no tiene qué enviar →
el agente continúa con las otras fuentes →
Ollama vuelve → el próximo fetch genera el resumen que faltaba
```

Esto funciona porque:
1. Cada fuente es independiente.
2. Los errores se persisten en la DB, no se propagan al proceso principal.
3. El retry es automático en el próximo ciclo.

---

## 10. El valor de la observabilidad directa

Tener el sistema en un homelab significa que puedes **inspeccionar cualquier componente
en tiempo real** sin permisos especiales ni dashboards externos:

```bash
# Estado del agente
systemctl --user status openclaw-gateway

# Logs del gateway
journalctl --user -u openclaw-gateway -f

# Estado de la DB
sqlite3 ~/.openclaw/tools.db "SELECT source, count(*), sum(content IS NOT NULL) FROM news_items GROUP BY source"

# Qué está corriendo en Ollama ahora mismo
curl http://192.168.50.113:11434/api/ps

# Chromium CDP: ver qué pestaña está activa
curl http://localhost:18800/json
```

Esta capacidad de inspección directa acelera el debugging de manera que ninguna
herramienta de observabilidad externa puede replicar completamente.

---

## Resumen: el stack multi-agente en un diagrama

```
                    Usuario (WhatsApp)
                          │
                    ┌─────▼──────┐
                    │  Gateway   │  OpenClaw + Ollama qwen3.5:9b
                    │  (skills)  │  systemd user service
                    └─────┬──────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐      ┌────▼────┐     ┌────▼────┐
    │Noticias │      │  TCG    │     │ Pokémon │
    │Agentes  │      │ Events  │     │  Daily  │
    └────┬────┘      └────┬────┘     └────┬────┘
         │                │               │
    CDP+RSS            CDP+API         API REST
    Ollama             SQLite          SQLite
    gemma4:e4b              │
         │                  │
    ┌────▼──────────────────▼──────────┐
    │         SQLite (local)           │
    │         tools.db                 │
    └────────────────┬─────────────────┘
                     │  sync incremental (post-send)
                     ▼
              ┌─────────────┐
              │  Postgres   │  Docker, 192.168.50.113
              │  (analítica)│  BI, dashboards, SQL
              └─────────────┘
```

---

## ¿Por dónde empezar?

Si quieres replicar algo similar:

1. **Empieza con Ollama**: instala un modelo local y haz tus primeras llamadas desde Python.
   La curva de aprendizaje es mínima si ya usas la API de OpenAI (misma interfaz).

2. **Un skill simple**: un agente que responde preguntas sobre un dataset local es suficiente
   para entender el ciclo completo.

3. **Agrega un canal real**: conectar el agente a WhatsApp o Telegram cambia completamente
   la forma en que interactúas con él. De notebook a sistema real.

4. **Itera en producción**: no esperes que todo esté perfecto. Los bugs más importantes
   los encuentras cuando el sistema corre de verdad, no en tests.

5. **Escribe los watchdogs al principio**: no después. Los procesos caen más de lo que
   esperas, especialmente con WhatsApp.

---

La tecnología de agentes está evolucionando rápido, pero los fundamentos —persistencia,
observabilidad, tolerancia a fallos, separación de responsabilidades— son los mismos
de siempre. El homelab es el lugar perfecto para aprenderlos sin presión de producción
y sin costo de nube.

---

*← [Persistencia y observabilidad](05-persistencia.md) | [Inicio de la serie](00-indice.md)*
