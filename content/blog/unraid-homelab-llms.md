Title: Unraid: el sistema operativo para tu homelab de LLMs
Date: 2026-05-02
Category: blog
Slug: unraid-homelab-llms

> **Serie:** Sistemas Multi-Agente en tu Homelab — Post 2 de 8

---

Cuando el homelab crece más allá de una Raspberry Pi y una PC de escritorio, la gestión
de servicios se vuelve caótica: ¿en qué máquina está corriendo Ollama? ¿Dónde montaste
Postgres? ¿Por qué el disco del servidor está al 94%? **Unraid** es la respuesta a estos
problemas antes de que aparezcan.

---

## Qué es Unraid

Unraid es un sistema operativo para servidores NAS (Network Attached Storage) y homelab
que combina tres cosas en un solo sistema:

1. **Gestión de almacenamiento** — múltiples discos con paridad, sin RAID tradicional
2. **Virtualización** — VMs con KVM/QEMU con acceso directo a GPU (passthrough)
3. **Contenedores Docker** — interfaz gráfica para gestionar todos tus servicios

No es un NAS puro (como FreeNAS/TrueNAS) ni un hypervisor puro (como Proxmox). Es
la intersección de ambos, optimizada para homelabs donde quieres **almacenamiento,
VMs y contenedores conviviendo en el mismo servidor**.

```
┌─────────────────────────────────────────────────────┐
│  UNRAID SERVER                                      │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Array de   │  │    Docker    │  │    VMs    │ │
│  │   discos    │  │  containers  │  │  (KVM)    │ │
│  │  (paridad)  │  │              │  │           │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  WebUI en http://tower.local                        │
└─────────────────────────────────────────────────────┘
```

---

## El modelo de almacenamiento: por qué no es RAID

El RAID tradicional requiere discos idénticos y pierde capacidad en paridad. Unraid
funciona diferente: puedes mezclar discos de cualquier tamaño, y solo necesitas **un
disco de paridad** que sea igual o mayor al disco más grande del array.

```
RAID 5 (tradicional):
  4 × 4TB = 12TB usables (25% overhead de paridad)
  Todos los discos deben ser del mismo tamaño

Unraid Array:
  1 × 4TB (paridad)
  1 × 4TB + 1 × 3TB + 1 × 2TB + 1 × 1TB = 10TB usables
  Puedes mezclar lo que tengas
```

La ventaja práctica: si falla un disco, solo pierdes los datos de ese disco. Los demás
siguen accesibles mientras reconstruyes. Y puedes ir añadiendo discos de lo que tengas
disponible sin planificar el array de antemano.

---

## Docker con GUI: el caso de uso más valioso para LLMs

La killer feature de Unraid para un homelab de LLMs es su **interfaz gráfica para Docker**.
En lugar de mantener `docker-compose.yml` a mano y acordarte de qué flags le pasaste a
cada contenedor, tienes un panel donde ves, arrancas, paras y actualizas todos tus servicios.

Servicios que correrías en Unraid para un setup como el nuestro:

| Servicio | Imagen Docker | Para qué |
|----------|---------------|----------|
| **Ollama** | `ollama/ollama` | LLM backend con GPU passthrough |
| **Open WebUI** | `ghcr.io/open-webui/open-webui` | Interfaz web para Ollama |
| **Postgres** | `postgres:18` | Replica analítica de SQLite |
| **Metabase** | `metabase/metabase` | Dashboards sobre los datos del agente |
| **Portainer** | `portainer/portainer-ce` | Gestión avanzada de contenedores |
| **Watchtower** | `containrrr/watchtower` | Auto-update de imágenes Docker |
| **Uptime Kuma** | `louislam/uptime-kuma` | Monitoreo de disponibilidad de servicios |

Cada uno de estos ya tiene una "template" en la comunidad de Unraid (Community Apps):
instalación con un clic, sin tocar la línea de comandos.

---

## GPU passthrough: Ollama con toda la VRAM disponible

El caso más interesante para LLMs es el **GPU passthrough a una VM o contenedor**. En
un setup típico de escritorio, la GPU está siendo usada por el sistema operativo host.
Con Unraid:

```
Unraid Host (sin GPU)
    │
    ├── VM: Windows (con GPU 1 — para juegos)
    └── Docker: Ollama (con GPU 2 — para LLMs)
```

Puedes asignar una GPU físicamente a Ollama y otra a una VM de Windows. El hypervisor
de Unraid gestiona el acceso exclusivo a cada GPU. Esto significa que Ollama tiene
acceso **directo** a la VRAM sin overhead de virtualización.

Para habilitar en el contenedor de Ollama:

```
Extra Parameters: --gpus all
```

Unraid detecta automáticamente las GPUs disponibles (NVIDIA y AMD vía ROCm) y las expone
a los contenedores que lo soliciten.

---

## Shares: el sistema de archivos compartido

Unraid expone el almacenamiento como **shares** — carpetas compartidas accesibles por SMB
(Windows), NFS (Linux/macOS) o por los propios contenedores Docker.

Para nuestro setup, un share `appdata` con subcarpetas por servicio es el patrón estándar:

```
/mnt/user/appdata/
├── ollama/          → modelos de Ollama (pueden ser 20-50GB)
├── postgres/        → datos de Postgres
├── open-webui/      → historial de conversaciones
└── openclaw/        → workspace del agente
```

Cada contenedor Docker monta su carpeta de `appdata` como volumen persistente. Cuando
actualizas el contenedor, los datos persisten. Cuando el servidor se reinicia, todo vuelve
al estado anterior automáticamente.

---

## Cómo encajaría en nuestra arquitectura

Nuestra setup actual tiene Ollama y Postgres corriendo directamente en un PC de escritorio
con Linux. Con Unraid, la misma arquitectura se vería así:

```
                    Antes (PC escritorio con Linux)
                    ─────────────────────────────
                    Ollama: proceso systemd
                    Postgres: docker manual
                    Sin gestión de discos
                    Backups: manual / ninguno


                    Con Unraid
                    ──────────
                    Ollama: contenedor Docker con GPU passthrough
                    Postgres: contenedor Docker con volumen en array
                    Array de discos con paridad automática
                    Backups: Unraid Backup Plugin / rsync a share
```

Las ventajas concretas para nuestro caso de uso:

**1. Centralización de modelos**
Los modelos de Ollama pueden pesar 4-50GB cada uno. Con Unraid, viven en el array de
discos con paridad. Si falla el SSD donde tenías los modelos, no los pierdes.

**2. Observabilidad del servidor**
Unraid tiene dashboard de uso de CPU, RAM, red y temperatura de discos. Cuando Ollama
está bajo carga pesada, ves exactamente cuánta VRAM y RAM está consumiendo.

**3. Actualizaciones sin downtime**
Community Apps notifica cuando hay una nueva versión de Ollama o Postgres. Actualizar
es un clic. El contenedor viejo para, el nuevo arranca con los mismos volúmenes.

**4. VMs para experimentar**
¿Quieres probar una distro nueva, un entorno de desarrollo aislado, o Windows para algo
específico? Creas una VM, la pruebas, la borras. Sin tocar el sistema host.

---

## Limitaciones que hay que conocer

Unraid no es perfecto. Antes de adoptarlo:

- **Licencia de pago**: ~$69-$129 USD one-time (por cantidad de discos). No es open source.
- **El array no es rápido**: diseñado para capacidad, no para IOPS. Para bases de datos
  o modelos que se cargan frecuentemente, usa un **cache pool** (SSDs NVMe fuera del array).
- **Curva de aprendizaje**: la primera configuración (asignar paridad, crear shares, configurar
  el cache pool) toma un fin de semana. Después de eso, prácticamente no requiere mantenimiento.
- **No es para producción crítica**: Unraid es excelente para homelab. Para infraestructura
  empresarial con SLAs, usa soluciones dedicadas.

---

## El cache pool: donde van los datos calientes

Para los servicios que necesitan acceso rápido a disco (Ollama cargando modelos, Postgres
en escritura), Unraid permite un **cache pool** de SSDs NVMe separado del array de HDDs:

```
Cache Pool (NVMe SSDs — rápido, sin paridad)
  └── /mnt/cache/appdata/    ← contenedores Docker aquí

Array de discos (HDDs + paridad — lento, con redundancia)
  └── /mnt/user/media/       ← datos fríos, backups, modelos grandes
```

Los modelos de Ollama que usas frecuentemente van en el cache. Los modelos que rara vez
usas van en el array. Unraid puede mover archivos automáticamente entre cache y array
según políticas configurables.

---

## Por dónde empezar

Si tienes un PC que puedes dedicar a servidor:

1. **Descarga Unraid OS** desde unraid.net y arranca desde USB (el sistema corre en RAM).
2. **Instala Community Apps** (plugin que agrega el store de templates Docker).
3. **Configura el array** con los discos que tengas disponibles.
4. **Instala Ollama** desde Community Apps con GPU passthrough activado.
5. **Instala Open WebUI** para tener interfaz web inmediatamente.

En menos de 2 horas puedes tener un servidor Ollama con interfaz web, accesible desde
cualquier dispositivo de tu red local.

---

## ¿Vale la pena si ya tienes una setup funcional?

Si tu setup actual funciona (Ollama en un PC, servicios corriendo), Unraid es una mejora
de operabilidad, no de funcionalidad. Te da:

- Gestión visual de contenedores en lugar de SSH + comandos
- Protección de datos en el array
- Facilidad para añadir o quitar servicios
- Monitoreo del servidor sin instalar nada extra

Para un equipo o presentación donde quieres mostrar el homelab a otros, la UI de Unraid
es mucho más accesible que un servidor Linux con `docker ps`. Para trabajo individual
donde ya conoces los comandos, el valor es menor.

La pregunta clave: **¿cuánto tiempo pasas manteniendo la infraestructura vs. usándola?**
Si la respuesta es "demasiado", Unraid reduce ese overhead significativamente.

---

*← [Skills, tools y agentes](07-skills-tools-y-agentes.md) | [Inicio de la serie](00-indice.md)*
