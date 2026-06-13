# slides/

Carpeta única para todo lo relacionado con slides del sitio oglabs. Mismo
patrón que `photos/` (fuente top-level) → `content/photos/` (servido): acá vive
la **fuente**, el build copia/renderiza lo que Pelican sirve.

## Contenido

| Archivo / dir        | Qué es                                                        | En git |
|----------------------|---------------------------------------------------------------|--------|
| `homelab.html`       | Deck reveal.js **en vivo** (`/slides/homelab.html`)           | sí     |
| `generate_slides.py` | Generador Marp de la serie "Sistemas Multi-Agente" (8 decks)  | sí     |
| `marp/`              | Output del generador (`.md` + `.html`) — regenerable, ignorado | no     |

## Deck en vivo (`homelab.html`)

Es la fuente de verdad. Pelican solo sirve estáticos bajo `content/`, así que
`make slides` lo copia a `content/slides/homelab.html` antes de cada build
(`make build` ya depende de `slides`). `content/slides/` es artefacto de build
y está en `.gitignore`. Editá siempre `slides/homelab.html`, nunca la copia.

El nav del tema lo enlaza en `themes/oglabs/templates/base.html`.

## Serie Marp (`generate_slides.py` + `marp/`)

La fuente de verdad es el dict `DECKS` embebido inline en `generate_slides.py`.
`marp/` es output efímero (ignorado en git); se recrea corriendo:

```bash
python slides/generate_slides.py   # escribe marp/*.md y renderiza marp/*.html con marp-cli (npx)
```

Esta serie **no se publica** todavía. Si en el futuro se publica, agregar un
paso de staging hacia `content/` como el de `homelab.html`.
