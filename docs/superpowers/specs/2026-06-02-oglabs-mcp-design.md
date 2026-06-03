# Diseño: MCP server para oglabs

**Fecha:** 2026-06-02
**Estado:** Aprobado para implementación

## Objetivo

Exponer las capacidades del sitio estático **oglabs** (Pelican → S3/CloudFront)
como un servidor **MCP** accesible por red, para que agentes de IA corriendo en
otros hosts de la LAN puedan gestionar contenido, ejecutar el pipeline LLM/imágenes
y construir/publicar el sitio.

## Decisiones de diseño

| Tema | Decisión |
|------|----------|
| Lenguaje / SDK | Python, SDK oficial `mcp` (FastMCP) |
| Transporte | streamable-HTTP, `0.0.0.0:<puerto>`, sin autenticación |
| Puerto | `OGLABS_MCP_PORT`, default `8765`; endpoint `http://<host>:8765/mcp` |
| Reutilización de lógica | Híbrido: contenido en Python puro; pipeline y build/deploy vía subprocess |
| deploy/publish | Expuestos sin guarda (mismo comportamiento que `make deploy/publish`) |
| Ejecución | Contenedor Docker en Unraid; repo montado como volumen |
| Credenciales | `.env` montado vía `env_file` (incluye claves LLM + AWS) |

## Arquitectura

Un único módulo `mcp_server.py` en la raíz del repo. Usa `FastMCP` para declarar
las tools y arranca con transporte streamable-HTTP. El proceso fuerza el CWD a la
raíz del repo (donde están `Makefile`, `scripts/`, `content/`, `drafts/`) para que
los scripts existentes funcionen con sus rutas relativas.

El servidor es un proceso sin estado: cada tool opera sobre el sistema de archivos
del repo (montado como volumen) o lanza subprocess. No mantiene sesión ni caché.

### Componentes internos

- **Helpers de rutas** (`_repo_path`, `_validate_section`): resuelven y validan que
  toda ruta de contenido quede dentro del repo y que `section` ∈ {`blog`, `projects`, `photos`}.
- **Helper de subprocess** (`_run`): ejecuta un comando con CWD = raíz del repo,
  captura stdout/stderr y devuelve `{ok, returncode, stdout, stderr}`.
- **Declaración de tools**: funciones decoradas con `@mcp.tool()`.

## Superficie de tools

### Contenido (Python puro, operaciones de archivo)

- `list_drafts(section: str | None) -> list[str]` — rutas de `.md` bajo `drafts/`.
- `list_posts(section: str | None) -> list[str]` — rutas de `.md` bajo `content/`.
- `read_post(path: str) -> dict` — devuelve `{frontmatter: dict, body: str}` de un `.md`.
- `create_draft(section: str, title: str) -> str` — replica `make draft`: genera slug
  (lowercase, no-alfanumérico → `-`), escribe `drafts/<section>/<slug>.md` con
  frontmatter `Title/Date/Category/Slug`. Devuelve la ruta creada.
- `write_draft(section: str, slug: str, content: str) -> str` — escribe/sobrescribe
  el contenido completo de un draft. Devuelve la ruta.

### Pipeline (subprocess a `python scripts/...`)

- `improve_writing(section: str, llm: str | None, overwrite: bool) -> dict`
  → `scripts/improve_writing.py --section <s> [--llm <l>] [--no-overwrite]`.
- `optimize_images(force: bool) -> dict` → `scripts/optimize_images.py [--force]`.
- `process_photos(llm: str | None, force: bool) -> dict`
  → `scripts/photo_pipeline.py [--llm <l>] [--force]`.

### Build & deploy (subprocess a `make`)

- `build() -> dict` → `make build`.
- `deploy() -> dict` → `make deploy`.
- `publish() -> dict` → `make publish`.

Todas las tools de subprocess devuelven el resultado estructurado de `_run`.

## Flujo de datos

1. Agente remoto se conecta a `http://<host>:8765/mcp` y descubre las tools.
2. Para contenido: la tool lee/escribe archivos `.md` directamente en el volumen montado.
3. Para pipeline/build/deploy: la tool lanza subprocess; el subprocess lee `.env`
   (claves LLM, S3, CloudFront) y opera sobre el repo. El resultado vuelve estructurado.
4. El contenido nuevo queda en el repo del host, listo para `git commit` por el usuario.

## Manejo de errores

- **Validación**: sección inválida o ruta fuera del repo → la tool lanza
  `ValueError` con mensaje claro (se propaga como error MCP).
- **Subprocess**: nunca lanza por código de salida ≠ 0; devuelve
  `{ok: false, returncode, stdout, stderr}` para que el agente decida.
- **Archivo inexistente** en `read_post` → `ValueError`.

## Empaquetado y despliegue (Docker / Unraid)

- **`Dockerfile`**: base `python:3.12-slim`; instala `make` y AWS CLI vía apt,
  luego `pip install -r requirements.txt`. `WORKDIR /app`. `EXPOSE 8765`.
  CMD lanza `python mcp_server.py`.
- **Volumen**: el repo se monta en `/app` (no se hornea en la imagen) para que los
  cambios de contenido persistan en el host y `deploy` suba el contenido real.
- **`docker-compose.yml`**: mapea puerto `8765:8765`, monta el repo (ruta del host
  parametrizable vía variable, p.ej. `${OGLABS_REPO_PATH}:/app`), carga `.env` con
  `env_file`. Sirve también como referencia para la plantilla de Unraid.
- **Credenciales**: el `.env` del repo se extiende con
  `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` además de las
  claves LLM y `S3_BUCKET` / `CLOUDFRONT_DISTRIBUTION_ID` ya presentes.
- **`requirements.txt`**: añadir `mcp>=1.2`.
- **`make mcp`**: target opcional que lanza `python mcp_server.py` para desarrollo
  local sin Docker.

## Testing

- **Funciones de contenido**: pytest sobre un repo temporal (`tmp_path`) verificando
  `create_draft` (slug + frontmatter), `write_draft`, `list_*`, `read_post` y la
  validación de rutas/secciones.
- **Tools de subprocess**: mockear `subprocess.run` y verificar que se construye el
  comando correcto y que el resultado se estructura bien (incluido el caso de error).

## Fuera de alcance (YAGNI)

- Autenticación / tokens (se decidió HTTP plano por ahora).
- Guarda `dry_run` en deploy (se decidió exponer sin guarda).
- Tools de solo lectura/búsqueda avanzada sobre el sitio publicado.
- systemd (reemplazado por Docker).
