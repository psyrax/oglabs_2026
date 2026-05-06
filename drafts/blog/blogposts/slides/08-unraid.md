---
marp: true
theme: uncover
class: invert
paginate: true
style: |
  section {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 1.1rem;
  }
  section.title {
    text-align: center;
  }
  h1 { color: #7dd3fc; }
  h2 { color: #86efac; border-bottom: 1px solid #334155; padding-bottom: 0.3em; }
  code { background: #1e293b; color: #f8fafc; padding: 0.1em 0.4em; border-radius: 4px; }
  pre  { background: #0f172a; border-left: 3px solid #7dd3fc; }
  table { font-size: 0.85rem; }
  th { background: #1e3a5f; color: #7dd3fc; }
  .small { font-size: 0.8rem; }
---

<!-- class: title -->
# Unraid
## El sistema operativo para tu homelab de LLMs

---

## Qué es Unraid

```
┌─────────────────────────────────────────────┐
│  UNRAID SERVER                              │
│                                             │
│  ┌───────────┐  ┌──────────────┐  ┌──────┐ │
│  │  Array de │  │    Docker    │  │ VMs  │ │
│  │  discos   │  │  containers  │  │ KVM  │ │
│  │ (paridad) │  │   (con GUI)  │  │      │ │
│  └───────────┘  └──────────────┘  └──────┘ │
│                                             │
│  WebUI en http://tower.local                │
└─────────────────────────────────────────────┘
```

La intersección de NAS + hypervisor + Docker host.
Optimizado para homelabs, no para producción empresarial.

---

## Almacenamiento: mezcla discos de cualquier tamaño

```
RAID 5 tradicional:
  4 × 4TB = 12TB (mismo tamaño obligatorio)

Unraid Array:
  1 × 4TB (paridad)   ← solo necesitas 1 disco de paridad
  1 × 4TB + 1 × 3TB + 1 × 2TB + 1 × 1TB
  = 10TB usables con lo que ya tienes
```

Si falla un disco → solo pierdes los datos de ese disco.
Los demás siguen accesibles mientras reconstruyes.

---

## Docker con GUI: servicios para LLMs

| Servicio | Imagen | Para qué |
|----------|--------|----------|
| **Ollama** | `ollama/ollama` | LLM backend con GPU passthrough |
| **Open WebUI** | `open-webui/open-webui` | Interfaz web para Ollama |
| **Postgres** | `postgres:18` | Replica analítica |
| **Metabase** | `metabase/metabase` | Dashboards de datos del agente |
| **Uptime Kuma** | `louislam/uptime-kuma` | Monitoreo de servicios |

Community Apps = instalar cualquiera de estos con 1 clic.

---

## GPU passthrough: Ollama con VRAM dedicada

```
Unraid Host (sin GPU directa)
    │
    ├── VM: Windows (GPU 1 — para juegos/trabajo)
    └── Docker: Ollama (GPU 2 — para LLMs)
                Extra Parameters: --gpus all
```

Ollama tiene acceso **directo** a la VRAM sin overhead de virtualización.
Puedes dedicar una GPU entera al servidor LLM mientras otra
alimenta un escritorio Windows en la misma máquina.

---

## Cache pool: datos calientes vs. fríos

```
Cache Pool (NVMe SSDs — rápido, sin paridad)
  └── /mnt/cache/appdata/
      ├── ollama/      ← modelos que usas frecuente
      ├── postgres/    ← escrituras de DB
      └── open-webui/

Array de discos (HDDs + paridad — redundante, lento)
  └── /mnt/user/media/
      └── ollama/models/  ← modelos que rara vez usas
```

Unraid puede mover archivos entre cache y array automáticamente.

---

## Nuestra setup actual → con Unraid

```
HOY:                         CON UNRAID:
────────────────────         ────────────────────────
Ollama: proceso systemd  →   Contenedor Docker + GPU passthrough
Postgres: docker manual  →   Contenedor con volumen en array
Sin gestión de discos    →   Array con paridad automática
Backups: ninguno         →   Plugin de backup + rsync
Monitoreo: SSH + comandos→   Dashboard web
```

---

## ¿Vale la pena si ya tienes algo funcionando?

**Sí, si:**
- Pasas tiempo significativo manteniendo la infra vs. usándola
- Quieres mostrar el homelab a otros (la UI es muy accesible)
- Tienes varios discos de distinto tamaño sin protección de paridad
- Quieres VM + Docker + almacenamiento en una sola máquina

**No urgente si:**
- Tu setup funciona y eres el único usuario
- Solo tienes una máquina con un disco

**Limitaciones honestas:** licencia $69–$129 USD, curva de primera configuración (~1 fin de semana), no apto para SLAs de producción.
