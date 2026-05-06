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
# 10 lecciones aprendidas
## Patrones que vienen de fallas reales

---

## 1. Secuencialidad > Paralelismo

```bash
# ❌ 7 scrapers compitiendo por Ollama (una VRAM)
python3 mexico_noticias.py &
python3 gaming_noticias.py &
wait  # → timeouts, deadlocks, "database is locked"

# ✅ Uno a la vez — predecible, debuggeable
python3 mexico_noticias.py
python3 gaming_noticias.py
```

---

## 2. Separa fetch de send

```
❌ scrape → generar resumen → enviar WA (un solo proceso)
   Un fallo en el medio lo pierde todo

✅ fetch → DB → send
              ↑
         audit trail, re-enviable, consultable
```

---

## 3. Agrupa los reinicios

```
Restart #1: gateway inicia, adquiere lock libsignal
Restart #2: gateway inicia, ve lock → sesión corrupta

→ WhatsApp deja de funcionar hasta reconectar QR
```

**Regla:** todos los cambios de config → un solo restart.
Cooldown mínimo entre reinicios automatizados.

---

## 4. Watchdogs simples con cooldown

```bash
# evita reiniciar en loop si el problema persiste
if [ -f "$LOCKFILE" ]; then
    AGE=$(( $(date +%s) - $(cat $LOCKFILE) ))
    [ $AGE -lt 600 ] && exit 0   # cooldown 10 min
fi

if ! openclaw channels ping --channel whatsapp; then
    date +%s > "$LOCKFILE"
    systemctl --user restart openclaw-gateway
fi
```

---

## 5. Modelo correcto para cada tarea

| Tarea | Modelo | Por qué NO el grande |
|-------|--------|---------------------|
| Clasificar tipo de bloqueador | `qwen2.5vl:3b` | 2-3s vs 3-5 min |
| Resumir 20 titulares | `gemma4:e4b` | Suficiente capacidad |
| Razonamiento multi-paso | `qwen3.5:9b` | Contexto y tool use |
| Análisis de deck TCG | `gemma4:26b` | Precisión necesaria |

---

## 6. El prompt es código

- Vive en archivos, no hardcodeado en el script
- **Especificidad** > generalidad
- `num_predict` importa — los modelos de razonamiento piensan antes de responder
- Prueba con **inputs reales**, no solo ejemplos perfectos

---

## 7. Logs estructurados desde el principio

```python
def log(event: str, **kwargs):
    print(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "event": event, **kwargs
    }), file=sys.stderr)

log("fetch_complete", source="mexico", items=23, duration_s=45.2)
log("article_blocked", url=url, reason="captcha")
```

Filtrable con `jq`, importable a Postgres, conectable a cualquier sistema de observabilidad.

---

## 8. La DB como tablero de control del agente

```
news_items.synced_at = NULL       → pendiente de sync
news_items.block_reason = NULL    → pendiente de scraping
news_items.block_reason = 'paywall'   → skip permanente
news_items.block_reason = 'extract_failed' → reintentar
news_items.content IS NOT NULL    → extraído exitosamente
```

Estado de cualquier ítem = un SELECT. Retry = un UPDATE.

---

## 9. Diseña para el fallo parcial

```
Ollama caído → fetch falla → filas sin resumen
    → send de esa fuente no tiene qué enviar
    → agente continúa con las otras fuentes
    → Ollama vuelve → próximo fetch completa el resumen
```

**Componentes independientes + estado en DB = resiliencia natural**

---

## 10. Observabilidad directa del homelab

```bash
# Estado del agente
systemctl --user status openclaw-gateway

# ¿Qué modelo está corriendo ahora mismo?
curl http://192.168.50.113:11434/api/ps

# ¿Qué artículos no tienen contenido?
sqlite3 ~/.openclaw/tools.db \
  "SELECT source, count(*) FROM news_items \
   WHERE content IS NULL GROUP BY source"

# ¿Qué pestaña tiene Chromium?
curl http://localhost:18800/json
```
