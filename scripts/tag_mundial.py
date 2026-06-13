#!/usr/bin/env python3
"""Tag the World Cup 2026 project posts with `mundial` so the theme can group
them into the /projects/mundial/ subsection. Idempotent: safe to re-run."""
import pathlib

FILES = [
    "mundial-2026-modelo-bayesiano-jer-rquico-altitud-primera-ronda.md",
    "mundial-2026-predicciones-del-12-de-junio-debutan-canad-y-estados-unidos.md",
    "mundial-2026-pron-sticos-de-la-primera-ronda.md",
    "predicci-n-de-resultados-del-mundial-2026-con-xgboost-v2.md",
    "predicci-n-de-resultados-del-mundial-2026-con-xgboost-v3.md",
    "predicci-n-de-resultados-del-mundial-2026-con-xgboost-v4.md",
    "predicciones-vs-resultados-modelos-mundial-2026-verificaci-n-en-vivo.md",
    "wc2026-primera-ronda-dual-model.md",
]


def main() -> None:
    base = pathlib.Path("content/projects")
    for name in FILES:
        p = base / name
        if not p.is_file():
            print("MISSING", name)
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        end = next((i for i, l in enumerate(lines) if l.strip() == ""), len(lines))
        meta = lines[:end]
        tag_idx = next(
            (i for i, l in enumerate(meta) if l.lower().startswith("tags:")), None
        )
        changed = False
        if tag_idx is None:
            ins = next(
                (i for i, l in enumerate(meta) if l.lower().startswith("title:")), 0
            ) + 1
            lines.insert(ins, "Tags: mundial")
            changed = True
        else:
            vals = [t.strip() for t in meta[tag_idx].split(":", 1)[1].split(",") if t.strip()]
            if "mundial" not in [v.lower() for v in vals]:
                vals.append("mundial")
                lines[tag_idx] = "Tags: " + ", ".join(vals)
                changed = True
        if changed:
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("OK" if changed else "ALREADY", name)


if __name__ == "__main__":
    main()
