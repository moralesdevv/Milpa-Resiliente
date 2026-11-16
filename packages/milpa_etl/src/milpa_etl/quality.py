import pandas as pd

z = "data/curated/chiquimula_prueba"
cov = pd.read_parquet(f"{z}/coverage.parquet")
d = pd.read_parquet(f"{z}/daily.parquet")

print("== Faltantes por variable, 2001-2025 ==")
t = cov.groupby("variable")[["n_expected", "n_valid"]].sum()
t["pct_missing"] = (100 * (1 - t.n_valid / t.n_expected)).round(2)
print(t, "\n")

print("== Los 10 peores variable-año ==")
print(cov.sort_values("pct_missing", ascending=False).head(10), "\n")

print("== Banderas de calidad (días) ==")
for nombre, bit in {"1 faltante": 1, "2 fuera de rango": 2,
                    "4 relleno": 4, "16 radiación modelada": 16}.items():
    print(f"{nombre}: {int(((d.qc_flags & bit) > 0).sum())}")
print(f"días con alguna bandera: {int((d.qc_flags > 0).sum())} de {len(d)}\n")

print("== Lluvia y ET0 anuales (mm) ==")
a = pd.DataFrame({
    "lluvia_mm": d.precip_mm.groupby(d.index.year).sum(),
    "dias_con_lluvia_dato": d.precip_mm.groupby(d.index.year).count(),
    "et0_mm": d.et0_mm.groupby(d.index.year).sum(),
}).round(0)
print(a, "\n")

print("== Ruta de ea usada (días) ==")
print(d.ea_method.value_counts())