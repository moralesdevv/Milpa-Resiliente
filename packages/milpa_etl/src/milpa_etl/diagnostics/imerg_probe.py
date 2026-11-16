#!/usr/bin/env python3
"""imerg_probe.py — sonda de UN día de IMERG Final para cerrar DP-16 con hechos.

No escribe en la base ni en el manifiesto. Descarga un archivo diario a
data/raw/IMERG_PROBE/ y IMPRIME lo que realmente trae: variables, unidades,
valor de relleno, rejilla, convención de tiempo y la celda de tu punto.
Con esa salida se escribe el conector real sin suposiciones.

Requisitos (una sola vez, en tu .venv):
    pip install earthaccess xarray h5netcdf
Credenciales: variable de entorno EARTHDATA_TOKEN (token de Earthdata Login),
o EARTHDATA_USERNAME y EARTHDATA_PASSWORD. NO pegues el token en el chat.
    export EARTHDATA_TOKEN=...      (Git Bash)

Uso:
    python imerg_probe.py --lat 14.8 --lon -89.5
    python imerg_probe.py --lat 14.8 --lon -89.5 --date 2022-10-05
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

# [Verificar] DP-16: confirmar en la ficha oficial de GES DISC.
SHORT_NAME = "GPM_3IMERGDF"      # IMERG Final, diario
VERSION = "07"


def load_dotenv(path=".env"):
    """Lector mínimo de .env (sin dependencias). No pisa variables ya definidas."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--date", default="2025-01-02", help="día a probar (YYYY-MM-DD)")
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "data"))
    a = ap.parse_args()

    load_dotenv()
    try:
        import earthaccess
        import xarray as xr
    except ImportError as e:
        sys.exit(f"ERROR: falta un paquete ({e}). Ejecuta: pip install earthaccess xarray h5netcdf")

    if not (os.environ.get("EARTHDATA_TOKEN")
            or (os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))):
        sys.exit("ERROR: define EARTHDATA_TOKEN (o EARTHDATA_USERNAME y EARTHDATA_PASSWORD) en el entorno o en .env")

    auth = earthaccess.login(strategy="environment")
    print("Login Earthdata:", "OK" if getattr(auth, "authenticated", True) else "FALLÓ")

    res = earthaccess.search_data(short_name=SHORT_NAME, version=VERSION,
                                    temporal=(a.date, a.date), count=5)
    print(f"\nBúsqueda {SHORT_NAME} v{VERSION} para {a.date}: {len(res)} resultado(s)")
    if not res:
        sys.exit("Sin resultados: el nombre del producto o la versión [Verificar] no coinciden. "
                    "Busca el producto en https://disc.gsfc.nasa.gov y corrige SHORT_NAME / VERSION.")
    g = res[0]
    try:
        umm = g["umm"]
        print("Colección:", umm.get("CollectionReference"))
        print("Tamaño (MB):", g.size())
    except Exception:  # noqa: BLE001
        pass

    out_dir = Path(a.data_dir) / "raw" / "IMERG_PROBE"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = earthaccess.download(res[:1], str(out_dir))
    if not files:
        sys.exit("ERROR: no se pudo descargar el archivo.")
    f = Path(files[0])
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    print(f"\nArchivo: {f.name}\nSHA-256: {sha}\nTamaño: {f.stat().st_size/1e6:.1f} MB")

    ds = None
    for group in (None, "Grid"):
        try:
            ds = xr.open_dataset(f, group=group) if group else xr.open_dataset(f)
            if ds.data_vars:
                print(f"\nDataset abierto (grupo: {group or 'raíz'})")
                break
        except Exception as e:  # noqa: BLE001
            print(f"(no se pudo abrir grupo {group or 'raíz'}: {e})")
    if ds is None or not ds.data_vars:
        sys.exit("ERROR: no pude leer variables del archivo; pega este error.")

    print("\n--- Variables ---")
    for name, v in ds.data_vars.items():
        print(f"{name:32s} dims={v.dims} units={v.attrs.get('units')!r} "
                f"fill={v.attrs.get('_FillValue', v.encoding.get('_FillValue'))!r}")
    print("\n--- Coordenadas ---")
    for c in ds.coords:
        v = ds[c]
        try:
            print(f"{c:10s} n={v.size} min={v.values.min()} max={v.values.max()}")
        except Exception:  # noqa: BLE001
            print(f"{c:10s} {v.values}")
    print("\nAtributos globales relevantes:")
    for k in ("ProductionTime", "title", "Conventions", "TemporalRange", "NorthBoundingCoordinate"):
        if k in ds.attrs:
            print(f"  {k}: {ds.attrs[k]}")

    # Celda del punto
    latn = next((n for n in ds.coords if n.lower().startswith("lat")), None)
    lonn = next((n for n in ds.coords if n.lower().startswith("lon")), None)
    if latn and lonn:
        lat_c = float(ds[latn].sel({latn: a.lat}, method="nearest"))
        lon_c = float(ds[lonn].sel({lonn: a.lon}, method="nearest"))
        step = abs(float(ds[latn].values[1] - ds[latn].values[0]))
        print(f"\nPunto consultado: ({a.lon}, {a.lat})")
        print(f"Centro de celda más cercano: ({lon_c:.3f}, {lat_c:.3f})  paso={step:.3f}°")
        print(f"Huella aproximada: lon [{lon_c-step/2:.3f}, {lon_c+step/2:.3f}]  "
                f"lat [{lat_c-step/2:.3f}, {lat_c+step/2:.3f}]")
        for name, v in ds.data_vars.items():
            if "prec" in name.lower() or "rain" in name.lower():
                pt = v.sel({latn: lat_c, lonn: lon_c})
                print(f"Valor {name} en esa celda:", pt.values.ravel()[:5], v.attrs.get("units"))
    print("\nListo. Pega esta salida completa (sin el token).")


if __name__ == "__main__":
    main()
