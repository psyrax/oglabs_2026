# Prompt: otra sesión de Claude escribe un blog post vía el MCP

Copia/pega lo siguiente en una sesión de Claude Code (en otro host de la LAN).

---

## Tarea: escribir un blog post en oglabs usando su MCP

### 1. Conecta el MCP (una sola vez)
El sitio oglabs expone un servidor MCP por HTTP en la LAN (sin auth). Regístralo:

```bash
claude mcp add --transport http oglabs http://192.168.50.113:8765/mcp
```

Verifica con `/mcp` que aparece "oglabs" y sus tools:
- Contenido: `create_draft`, `write_draft`, `list_drafts`, `list_posts`, `read_post`
- Pipeline: `improve_writing`, `optimize_images`, `process_photos`
- Build/deploy: `build`, `deploy`, `publish`

### 2. Contexto: qué se construyó (esto es el tema del post)
En sesiones anteriores se hizo lo siguiente sobre el sitio oglabs (Pelican → S3/CloudFront, corriendo en un homelab Unraid):

1. **Se creó un servidor MCP** (`mcp_server.py`, FastMCP + transporte streamable-HTTP) para que agentes de IA en otros hosts de la LAN puedan operar el blog de forma remota: crear/editar drafts, correr el pipeline de imágenes/LLM, y hacer build/deploy a S3+CloudFront.
2. **Se empaquetó en Docker** y se desplegó en el host Unraid `192.168.50.113:8765`, con el repo montado como volumen y una plantilla XML nativa de Unraid para administrarlo desde su UI. Se añadió `make sync-host` para redeploy en un paso (rsync + rebuild + restart).
3. **Se endureció la seguridad** de las tools de contenido (validación de rutas para que no se pueda leer `.env` ni escapar de drafts/content), tras una revisión de seguridad automática.
4. **Se migró todo el backend LLM de OpenAI a modelos cloud de Ollama** (servidos por el Ollama del homelab en `192.168.50.113`, autenticado con ollama.com): mejora de texto con `kimi-k2.6:cloud`, descripción de fotos con `qwen3-vl:235b-cloud`, y las "tres memorias falsas" de cada foto generadas por `qwen3-vl:235b-cloud`, `gemma4:31b-cloud` y `kimi-k2.6:cloud`. Se eliminó la dependencia de OpenAI por completo.

### 3. Escribe el post
- Idioma: **español** (es la lengua del blog). Tono técnico, cercano, en primera persona ("construimos…", "decidimos…"), como los posts de la serie homelab existentes. Revisa el estilo con `list_posts("blog")` + `read_post(...)` de 1-2 posts para imitar voz y formato.
- Crea el draft con la tool: `create_draft(section="blog", title="<un título atractivo>")`. Te devuelve la ruta `drafts/blog/<slug>.md`.
- Escribe el contenido completo con `write_draft(section="blog", slug="<slug>", content="<markdown>")`. Mantén el frontmatter de Pelican al inicio (Title, Date, Category: blog, Slug). Cuenta la historia de los 4 puntos de arriba: el porqué (agentes remotos operando el blog), las decisiones de arquitectura (MCP HTTP, Docker en Unraid, sin auth en LAN y sus trade-offs), y la migración a Ollama cloud.
- Longitud orientativa: 700–1200 palabras. Incluye algún bloque de código (ej. el `claude mcp add`, o la lista de tools).

### 4. Publica (pregunta antes de deployar)
- Previsualiza generando el sitio: `build()` y revisa que no haya errores.
- **Antes de `deploy()`/`publish()` (suben a producción real en S3), muestra el post y pide confirmación.**

Empieza listando posts existentes para captar el estilo, propón el título, y luego escribe el draft.

---

> Cambia el host si mueves el MCP de `192.168.50.113`. Recuerda que `deploy`/`publish` publican a producción y el MCP no tiene auth — por eso se pide confirmación antes de publicar.
