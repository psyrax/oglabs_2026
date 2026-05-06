Title: ¿Qué es OpenClaw?
Date: 2026-04-20
Category: blog
Slug: que-es-openclaw

Llevo un tiempo mencionando OpenClaw en este blog sin haberlo presentado formalmente. Este post es esa presentación: qué es, qué problema resuelve, y para quién tiene sentido.

---

## El problema que resuelve

Los LLMs son impresionantes generando texto, pero por sí solos son reactivos y sin memoria. Responden a un prompt y paran. Para construir algo útil —un asistente que te manda noticias cada mañana, un bot que consulta tu base de datos, un agente que hace scraping web cuando se lo pides— necesitas una capa que:

1. **Escuche** mensajes entrantes (de WhatsApp, Telegram, una API, lo que sea)
2. **Decida** qué hacer con cada mensaje
3. **Ejecute** acciones en el mundo real (consultar una DB, hacer scraping, llamar a una API)
4. **Responda** de vuelta al usuario

OpenClaw es esa capa.

---

## Qué es exactamente

OpenClaw es un framework de agentes conversacionales diseñado para correr en hardware propio —un servidor en casa, una Raspberry Pi, una VM— sin depender de APIs de pago ni de infraestructura en la nube.

Sus tres conceptos centrales:

**Gateway** — el proceso que nunca para. Mantiene conexiones persistentes con los canales de mensajería, gestiona el historial de conversación por usuario, y enruta cada mensaje al skill correcto.

**Skills** — módulos que definen qué puede hacer el agente. Cada skill tiene una descripción en lenguaje natural (que el router usa para decidir cuándo invocarlo), un prompt de sistema que configura el comportamiento del LLM, y herramientas (funciones Python o scripts) que el modelo puede llamar.

**Tools** — funciones concretas que el LLM puede invocar durante una conversación. `get_news()`, `search_database()`, `fetch_webpage()`. El LLM decide cuándo llamarlas; el skill define cuáles están disponibles.

---

## Cómo funciona en la práctica

```
Usuario en WhatsApp: "¿Qué noticias hay de tecnología hoy?"
         │
         ▼
Gateway: identifica el skill "noticias" por descripción semántica
         │
         ▼
LLM (Ollama local): decide llamar get_news(category="tech")
         │
         ▼
Tool: consulta SQLite local → devuelve 12 artículos
         │
         ▼
LLM: genera resumen legible en lenguaje natural
         │
         ▼
WhatsApp: "Hoy en tecnología: [resumen de 3 párrafos]"
```

Todo esto ocurre en segundos, corre completamente local, y el costo por consulta es cero.

---

## Por qué no LangChain / AutoGen / CrewAI

Esos frameworks son excelentes para prototipado y para sistemas que corren en cloud. OpenClaw tiene un foco diferente:

- **Mensajería real como ciudadano de primera clase**: WhatsApp, Telegram, no solo HTTP.
- **Diseñado para un nodo único**: sin coordinadores distribuidos, sin colas de mensajes, sin Kubernetes.
- **Proactivo además de reactivo**: el agente puede enviar mensajes sin que el usuario pregunte (noticias matutinas, alertas, resúmenes programados).
- **Modelos locales por defecto**: compatible con la API de Ollama (formato OpenAI), sin requerir claves de API externas.

No es mejor ni peor, es un punto diferente en el espacio de diseño.

---

## Qué hemos construido con él

En nuestro homelab, OpenClaw orquesta actualmente:

- **Agentes de noticias**: scraping de RSS y sitios web, resumen con LLM, envío diario a grupos de WhatsApp con audiencias distintas.
- **Eventos TCG**: recopilación de torneos de Pokémon TCG en CDMX, con enriquecimiento de datos vía scraping CDP.
- **Análisis de decks**: el usuario manda una lista de cartas por WhatsApp y el agente evalúa el deck.

Todo corriendo en un Raspberry Pi 5 como orquestador y un PC de escritorio con GPU como servidor de inferencia.

---

## Dónde seguir leyendo

Si esto te parece interesante, la [serie completa sobre sistemas multi-agente en homelab](/blog/serie-multiagente-homelab/) entra en detalle en la infraestructura, el código, y las lecciones aprendidas construyendo esto en producción.
