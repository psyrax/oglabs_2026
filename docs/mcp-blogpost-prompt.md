# Prompt genérico: un agente publica un blog post en oglabs vía el MCP

Copia/pega lo siguiente en una sesión de Claude Code (en cualquier host de la LAN).
Reemplaza `{{TEMA}}` por el tema del post; lo demás es reutilizable para cualquier tema.

---

## Tarea: escribir y publicar un blog post en oglabs usando su MCP

**Tema del post:** {{TEMA}}

### 1. Conecta el MCP (una sola vez)
El sitio oglabs expone un servidor MCP por HTTP en la LAN (sin auth). Regístralo:

```bash
claude mcp add --transport http oglabs http://192.168.50.113:8765/mcp
```

Verifica con `/mcp` que aparece "oglabs". Tools disponibles:
- Contenido: `create_draft`, `write_draft`, `publish_draft`, `list_drafts`, `list_posts`, `read_post`
- Pipeline: `improve_writing`, `optimize_images`, `process_photos`
- Build/deploy: `build`, `deploy`, `publish`

### 2. Capta el estilo del blog
- Lista los posts existentes: `list_posts("blog")`.
- Lee 1-2 con `read_post(...)` para imitar voz, formato y frontmatter.
- Convenciones: español, tono técnico y cercano, primera persona. Frontmatter de
  Pelican al inicio: `Title`, `Date`, `Category: blog`, `Slug`.

### 3. Escribe el draft
- Crea el archivo: `create_draft(section="blog", title="<título atractivo sobre {{TEMA}}>")`.
  Devuelve la ruta `drafts/blog/<slug>.md`.
- Escribe el contenido completo (incluido el frontmatter) con
  `write_draft(section="blog", slug="<slug>", content="<markdown>")`.
- Orientación: 700–1200 palabras, con al menos un bloque de código o ejemplo si el
  tema lo amerita. Estructura clara con encabezados.
- (Opcional) Si quieres pulido automático con el LLM del homelab, usa
  `improve_writing(section="blog")` — reescribe los drafts hacia `content/`.

### 4. Publica el draft al árbol de contenido
El sitio se construye **solo desde `content/`**, así que un draft no se publica
hasta promoverlo: `publish_draft(section="blog", slug="<slug>")` lo copia tal cual
a `content/blog/`. (Si usaste `improve_writing`, ese paso ya lo movió y puedes
saltarte este.)

### 5. Previsualiza y publica (pide confirmación antes de publicar)
- Genera el sitio: `build()` y revisa que no haya errores.
- **Antes de `deploy()` o `publish()` (suben a producción real en S3 +
  CloudFront), muestra el post al usuario y pide confirmación explícita.**
  (El deploy pasa un scrubber que redacta secretos del output antes de subir.)
- Atajo de un solo paso (tras confirmar): `publish_draft_live(section="blog",
  slug="<slug>")` promueve el draft y hace build + deploy de una.

Empieza listando posts existentes para captar el estilo, propón el título, escribe
el draft, y para antes de publicar.

---

> Cambia el host si mueves el MCP de `192.168.50.113`. El MCP no tiene auth y
> `deploy`/`publish` van a producción — por eso se confirma antes de publicar.
