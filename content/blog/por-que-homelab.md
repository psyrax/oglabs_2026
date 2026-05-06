Title: Por qué un homelab para experimentar con LLMs y agentes
Date: 2026-05-01
Category: blog
Slug: por-que-homelab

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 1 de 8

---

Cuando empezamos a explorar sistemas multi-agente, la primera tentación es usar la API de
OpenAI o Anthropic: fácil, sin fricción, documentación excelente. Y tiene sentido para
prototipos. Pero llegó un momento en que queríamos algo diferente: **correr experimentos
a las 3am sin miedo a la factura**, iterar rápido sin latencia de red, y sobre todo,
entender de verdad lo que pasa dentro de cada componente.

La respuesta fue montar un homelab dedicado a LLMs. Este post explica por qué vale la pena
y qué ventajas concretas hemos obtenido.

---

## El problema con "solo cloud"

Las APIs de LLMs son cómodas pero tienen fricciones reales cuando experimentas:

- **Costo por token**: una sesión de debugging de 4 horas puede costarte $10-30 sin que
  hayas producido nada útil todavía.
- **Latencia variable**: las APIs públicas tienen jitter. Un agente que dispara 20 llamadas
  encadenadas puede tardar 40 segundos por latencia de red aunque el modelo sea rápido.
- **Datos privados**: si tus datos de entrenamiento o experimentación son sensibles, enviarlos
  a un tercero es un bloqueador legal o de negocio.
- **Rate limits**: en la fase de "¿funciona esto?" necesitas iterar rápido. Los rate limits
  interrumpen ese flujo.
- **Dependencia de disponibilidad**: si el endpoint cae, tu demo cae.

---

## Qué ganas con hardware propio

### 1. Iteraciones ilimitadas sin costo marginal

Con Ollama corriendo localmente, cada llamada al modelo cuesta exactamente **cero dólares**.
Puedes correr el mismo prompt 500 veces para evaluar varianza de salida, probar temperaturas
distintas, o depurar un agente roto sin pensar en el medidor.

### 2. Latencia predecible y baja

Una llamada a `qwen3:0.6b` en hardware local puede contestar en 200ms. Para agentes que
encadenan 10+ llamadas en una tarea, eso es la diferencia entre 2 segundos y 20 segundos
de tiempo total de respuesta.

### 3. Modelos especializados sin permiso

La comunidad open-source (Hugging Face, Ollama Hub) tiene modelos para tareas específicas:
visión, código, idiomas, documentos. Puedes cambiar de modelo entre pasos de tu pipeline
sin solicitar acceso a nadie.

### 4. Control sobre el contexto completo

Cuando el agente falla, tienes acceso a **todo**: logs del modelo, prompts exactos, tokens
generados, tiempos de inferencia. Con una API externa solo ves lo que el proveedor expone.

### 5. Aprendes la infraestructura real

Configurar Ollama, montar servicios systemd, conectar una base de datos, escribir watchdogs:
estas son exactamente las habilidades que necesitas para llevar un sistema multi-agente
a producción. El homelab es el entorno de práctica.

---

## ¿Necesitas hardware caro?

No. Nuestra setup actual corre en dos máquinas modestas:

| Componente | Dispositivo | Rol |
|------------|-------------|-----|
| Orquestador / gateway | Raspberry Pi 5 (arm64) | OpenClaw gateway, crons, scripts Python |
| LLM server | PC de escritorio (Ryzen 5, AMD RX 9070 XT, 16GB VRAM) | Ollama con múltiples modelos |

El Pi consume ~5W idle. El servidor LLM solo prende cuando hay inferencia activa.
**El costo de electricidad mensual es menor que una sola sesión de debugging en GPT-4.**

---

## Cuándo sí tiene sentido usar cloud

El homelab no reemplaza todo. Usamos APIs externas cuando:

- Necesitamos un modelo de frontera (GPT-4o, Claude Opus) para tareas de alta precisión.
- El experimento es one-shot y montar la infraestructura no vale la pena.
- Necesitamos escalar horizontalmente rápido (múltiples usuarios concurrentes).

La clave es tener claridad sobre cuándo cada opción es la correcta, no casarse con ninguna.

---

## Lo que vamos a construir en esta serie

A lo largo de los siguientes posts vamos a diseccionar un sistema real que construimos:

- Un **gateway de agentes** que recibe mensajes de WhatsApp y los enruta a skills especializados.
- **Agentes de noticias** que hacen scraping web, procesan imágenes con un VLM, y generan
  resúmenes concisos.
- Un **pipeline de persistencia** SQLite → Postgres con sync incremental y observabilidad.
- Patrones para hacer todo esto **robusto**: reintentos, watchdogs, secuencialidad, manejo
  de anti-bot.

Empecemos por la infraestructura.

---

*Siguiente: [La infraestructura: hardware y servicios →](02-infraestructura.md)*
