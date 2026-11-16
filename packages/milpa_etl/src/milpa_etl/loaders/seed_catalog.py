#!/usr/bin/env python3
"""seed_catalogo.py — carga catalogs/crops.yaml a ref.* (idempotente).

Alcance de esta primera versión (sandbox):
  * registra ref.catalog_release (hash del contenido normalizado + git SHA)
  * hace upsert de ref.crop (identificación: código, nombres, familia, leguminosa)
  * NO carga variedades, etapas, raíces ni umbrales mientras tengan `pending`:
    ref.phenology_stage exige kc_start/kc_end NOT NULL y no se rellenan con
    valores inventados (principio P9). Solo informa qué quedó pendiente.

Uso:
    python seed_catalogo.py --catalog catalogs/crops.yaml --dry-run
    python seed_catalogo.py --catalog catalogs/crops.yaml
    Conexión: --database-url o variable DATABASE_URL
    (ej. postgresql://milpa:CLAVE@localhost:5432/milpa). Usa la misma que
    usa registrar_zona.py.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import yaml

REQUIRED = ("code", "name_es", "name_en", "family")


def is_pending(v):
    return v is None or (isinstance(v, str) and v.strip().lower() == "pending")


def count_pending(node):
    if isinstance(node, dict):
        return sum(count_pending(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_pending(v) for v in node)
    return 1 if isinstance(node, str) and node.strip().lower() == "pending" else 0


def load_catalog(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or not data.get("crops"):
        sys.exit("ERROR: el YAML no tiene la clave 'crops'.")
    seen = set()
    for c in data["crops"]:
        for k in REQUIRED:
            if is_pending(c.get(k)):
                sys.exit(f"ERROR: cultivo {c.get('code')!r} sin campo requerido '{k}'.")
        if c["code"] in seen:
            sys.exit(f"ERROR: código duplicado {c['code']!r}.")
        seen.add(c["code"])
    return data


def catalog_hash(data):
    canon = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "sin-git"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="catalogs/crops.yaml")
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = load_catalog(a.catalog)
    h = catalog_hash(data)
    sha = git_sha()

    n_var = sum(len(c.get("varieties") or []) for c in data["crops"])
    print(f"Catálogo: {a.catalog}  versión={data.get('catalog_version')}  estado={data.get('status')}")
    print(f"catalog_hash={h}")
    print(f"git_sha={sha}")
    print(f"Cultivos: {[c['code'] for c in data['crops']]}")
    print(f"Variedades en el YAML: {n_var} (no se cargan variedades con campos pending)")
    print(f"Campos 'pending' en el YAML: {count_pending(data['crops'])}")
    print(f"Decisiones pendientes: {data.get('pending_decisions', [])}")

    if a.dry_run:
        print("\n--dry-run: no se escribió nada en la base.")
        return

    if not a.database_url:
        sys.exit("ERROR: falta --database-url o la variable DATABASE_URL.")
    try:
        import psycopg
    except ImportError:
        sys.exit("ERROR: falta psycopg (pip install 'psycopg[binary]').")

    conn = psycopg.connect(a.database_url)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ref.catalog_release (catalog_hash, git_sha) "
                "VALUES (%s, %s) ON CONFLICT (catalog_hash) DO NOTHING",
                (h, sha),
            )
            for c in data["crops"]:
                fixes = c.get("fixes_n_conditions")
                fixes = None if is_pending(fixes) else fixes
                cur.execute(
                    """INSERT INTO ref.crop
                            (code, name_es, name_en, scientific_name, family,
                            is_legume, fixes_n_conditions)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (code) DO UPDATE SET
                            name_es=EXCLUDED.name_es, name_en=EXCLUDED.name_en,
                            scientific_name=EXCLUDED.scientific_name,
                            family=EXCLUDED.family, is_legume=EXCLUDED.is_legume,
                            fixes_n_conditions=EXCLUDED.fixes_n_conditions""",
                        (c["code"], c["name_es"], c["name_en"],
                        c.get("scientific_name"), c["family"],
                        c.get("is_legume"), fixes),
                )
        print("\nOK: catalog_release y ref.crop cargados (idempotente).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
