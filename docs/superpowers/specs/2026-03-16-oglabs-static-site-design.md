# oglabs — Sitio Estático Personal

**Fecha:** 2026-03-16
**Estado:** Aprobado

---

## Resumen

Sitio estático personal unificado con tres secciones: blog de pensamientos, proyectos de código y galería fotográfica con descripciones generadas por IA. Construido con Pelican (Python), alojado en AWS S3.

---

## Arquitectura

### Estructura de directorios

```
oglabs/
├── drafts/
│   ├── blog/              # Posts raw escritos por el autor
│   ├── projects/          # Proyectos raw escritos por el autor
│   └── images/            # Imágenes originales para posts (alta resolución, no se tocan)
├── content/
│   ├── blog/              # Solo posts mejorados por LLM (generados por improve_writing.py)
│   ├── projects/          # Solo proyectos mejorados por LLM (generados por improve_writing.py)
│   ├── images/            # Imágenes para posts de blog y proyectos (gestionadas manualmente)
│   └── photos/
│       ├── *.md           # Un .md por foto (generado por photo_pipeline.py)
│       └── images/        # Fotos optimizadas para web (generadas por photo_pipeline.py)
├── photos/
│   ├── originals/         # Fotos de cámara originales (alta resolución, no se tocan)
│   └── .processed_manifest.json  # Registro de fotos ya procesadas
├── themes/
│   └── oglabs/            # Tema Jinja2 custom oscuro/minimal
├── scripts/
│   ├── photo_pipeline.py   # Procesa fotos → llama IA → genera Markdown en content/photos/
│   ├── optimize_images.py  # Optimiza imágenes de drafts/images/ → content/images/
│   └── improve_writing.py  # Lee drafts/ → llama LLM → escribe en content/
├── pelicanconf.py
└── Makefile
```

### Tecnologías

- **SSG:** Pelican (Python)
- **Templates:** Jinja2 (tema custom)
- **Hosting:** AWS S3 (sitio estático)
- **Deploy:** `aws s3 sync`

---

## Secciones del sitio

### Home
- Hero fotográfico: la foto más reciente ocupa toda la pantalla de entrada
- Navegación discreta en la parte superior: `blog · proyectos · fotos`
- El nombre del sitio (`oglabs`) sobre la foto con tipografía liviana

### Fotos
- Una foto a la vez, pantalla completa
- Imagen a la izquierda (alta resolución, máxima calidad)
- Descripción generada por IA a la derecha (texto completo)
- Navegación con flechas (anterior / siguiente)

### Blog
- Lista minimal: título, fecha, extracto
- Sin imágenes de portada
- Ordenado cronológicamente (más reciente primero)
- Los posts pueden incluir imágenes inline en el cuerpo del texto usando `{static}/images/<nombre>`

### Proyectos
- Mismo layout que Blog: lista minimal
- Puede incluir etiquetas de lenguaje/tecnología
- Los proyectos pueden incluir imágenes inline igual que el blog

---

## Pipelines de contenido

### Pipeline de fotografías (`scripts/photo_pipeline.py`)

1. Determina fotos nuevas comparando `photos/originals/` contra `photos/.processed_manifest.json` (lista de archivos ya procesados)
2. Por cada foto nueva:
   a. Extrae metadata EXIF (fecha de captura, cámara, lente, ISO, apertura, velocidad)
   b. Genera versión optimizada para web en `content/photos/images/<nombre>.jpg` (JPEG, calidad 92, max 2400px en el lado más largo, preservando proporción)
   c. Llama a API de IA de visión para generar descripción (mismo backend que `improve_writing.py`: Ollama/Claude/OpenAI, configurable con `--llm` o `OGLABS_LLM`)
   d. Escribe `content/photos/<nombre>.md` con descripción, metadata EXIF y ruta relativa `{static}/photos/images/<nombre>.jpg`
3. Actualiza `photos/.processed_manifest.json`

> **Nota:** `content/photos/` contiene dos tipos de archivos: los `.md` que Pelican procesa como artículos, y el subdirectorio `images/` que Pelican copia como asset estático. Pelican solo convierte archivos `.md` en páginas; el resto de archivos y directorios en `STATIC_PATHS` se copian tal cual a `output/`.

#### "Foto más reciente" para el hero del home

Se determina por **fecha EXIF** (`DateTimeOriginal`). Si no hay EXIF disponible, se usa la fecha de modificación del archivo.

### Pipeline de optimización de imágenes de posts (`scripts/optimize_images.py`)

1. Determina imágenes nuevas comparando `drafts/images/` contra `drafts/.images_manifest.json`
2. Por cada imagen nueva:
   a. Genera versión optimizada en `content/images/<nombre>.jpg` (JPEG, calidad 85, max 1600px en el lado más largo)
3. Actualiza `drafts/.images_manifest.json`

Parámetros distintos a `photo_pipeline.py` (max 2400px, calidad 92) porque las imágenes de posts no necesitan la misma resolución que la galería fotográfica.

---

### Pipeline de mejora de escritura (`scripts/improve_writing.py`)

```bash
python scripts/improve_writing.py \
  --section blog|projects|all \
  --llm ollama|claude|openai
```

- Lee archivos `.md` desde `drafts/blog/` o `drafts/projects/`
- Envía el contenido al LLM configurado para mejorar redacción
- Guarda resultado en `content/blog/` o `content/projects/`
- Los originales en `drafts/` nunca se modifican
- **Solo el contenido mejorado y guardado en `content/` se publica**
- Si el archivo destino ya existe en `content/`, se **sobreescribe por defecto**. Usar `--no-overwrite` para omitir archivos existentes.

#### Backends LLM soportados

| Flag | Backend | Config requerida |
|------|---------|-----------------|
| `--llm ollama` | Ollama local | `OLLAMA_HOST` (default: localhost:11434) |
| `--llm claude` | Anthropic Claude | `ANTHROPIC_API_KEY` |
| `--llm openai` | OpenAI | `OPENAI_API_KEY` |

Los tres backends implementan la misma interfaz interna (`LLMClient`). Configurable también via variable de entorno `OGLABS_LLM`.

---

## Flujo de trabajo

### Publicar una foto nueva

```bash
# 1. Copiar foto a photos/originals/
cp ~/fotos/DSC_1234.jpg photos/originals/

# 2. Procesar
python scripts/photo_pipeline.py

# 3. Build y deploy
make build && make deploy
```

### Publicar un post del blog o proyecto

```bash
# 1. Escribir en drafts/
vim drafts/blog/mi-nuevo-post.md

# 2. Mejorar con LLM
python scripts/improve_writing.py --section blog --llm claude

# 3. Revisar el resultado en content/blog/mi-nuevo-post.md

# 4. Build y deploy
make build && make deploy
```

---

## Diseño visual

- **Fondo:** `#0d0d0d` (casi negro)
- **Texto principal:** `#cccccc`
- **Texto secundario / fechas:** `#555555`
- **Acentos:** mínimos, solo para navegación activa
- **Tipografía:** sans-serif liviana, mucho espacio en blanco
- **Principio:** las fotos hablan solas, el texto no compite

---

## Configuración de Pelican (`pelicanconf.py`)

Ajustes clave requeridos:

```python
THEME = 'themes/oglabs'

PATH = 'content'  # directorio base; ARTICLE_PATHS y STATIC_PATHS son relativos a este

# Rutas de contenido por sección
ARTICLE_PATHS = ['blog', 'projects', 'photos']

# Excluir el subdirectorio de imágenes para que Pelican no intente parsear .jpg como artículos
ARTICLE_EXCLUDE_PATHS = ['photos/images']

# URLs limpias por sección
ARTICLE_URL = '{section}/{slug}/'
ARTICLE_SAVE_AS = '{section}/{slug}/index.html'

# Imágenes estáticas: fotos de galería + imágenes de posts
STATIC_PATHS = ['photos/images', 'images']
```

Los artículos de blog usan `category: blog`, proyectos `category: projects`, y fotos `category: photos`. Pelican los separa en `/blog/`, `/projects/` y `/photos/`. Las imágenes en `content/photos/images/` son copiadas por Pelican como archivos estáticos a `output/photos/images/`.

---

## Makefile

```makefile
.PHONY: photos images build deploy publish

# Procesa fotos nuevas de galería (detecta cambios via manifest)
photos:
	python scripts/photo_pipeline.py

# Optimiza imágenes nuevas de posts (detecta cambios via manifest)
images:
	python scripts/optimize_images.py

# Build completo: fotos + imágenes de posts primero, luego Pelican
build: photos images
	pelican content -s pelicanconf.py -o output

# Deploy a S3
deploy:
	aws s3 sync output/ s3://$(S3_BUCKET)/ --delete

# Build + deploy en un paso
publish: build deploy
```

Uso: `S3_BUCKET=mi-bucket make publish`

El bucket S3 debe tener habilitado el hosting de sitio estático con `index.html` como documento raíz.

---

## Fuera del alcance (v1)

- Sistema de comentarios
- Búsqueda full-text
- Feed RSS (puede agregarse como plugin de Pelican en v2)
- Panel de administración web
- Múltiples idiomas
