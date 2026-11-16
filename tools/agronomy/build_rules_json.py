"""Genera regions/reglas_agronomicas_jocotan.json (v2) a partir de los hitos verificados.

Es una AYUDA de una sola vez para que las derivaciones de duración de etapas sean reproducibles y la suma
de etapas coincida con el ciclo total (se comprueba aquí y en pruebas). El JSON resultante es la fuente
central; para cambiar parámetros se edita el JSON, no este script ni el código del backend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ACCESSED = "2026-11-16"

# Proporciones FAO-56 Tabla 11 (días): maíz grano, Nigeria (húmedo), 125 d = 20/35/40/30;
# frijol seco, Pakistán/California, 95 d = 15/25/35/20.
FAO_MAIZE = (20, 35, 40, 30)
FAO_BEAN = (15, 25, 35, 20)


def split_days(total: int, weights: tuple[int, ...]) -> list[int]:
    """Reparte `total` días en proporción a `weights` (método del mayor resto; suma exacta)."""
    s = sum(weights)
    raw = [total * w / s for w in weights]
    out = [int(r) for r in raw]
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - out[i], -i), reverse=True)
    for i in order[: total - sum(out)]:
        out[i] += 1
    assert sum(out) == total
    return out


STAGES = ("Inicial", "Desarrollo", "Media", "Final")

SOURCES = {
    "FAO56": {
        "titulo": "FAO Irrigation and Drainage Paper 56, cap. 6: Tabla 11 (duración de etapas) y Tabla 12 (Kc únicos)",
        "institucion": "FAO",
        "url": "https://www.fao.org/4/x0490e/x0490e0b.htm",
        "consultado": ACCESSED,
        "nota": "Kc ini de maíz está en una imagen de la tabla: valor 0.30 de la tabla publicada, no leído por extracción de texto; verificar contra el original.",
    },
    "ICTA_MAIZ_ORIENTE_2015": {
        "titulo": "Recomendaciones técnicas para el cultivo de maíz en el oriente de Guatemala (Chiquimula, El Progreso, Jalapa, Jutiapa, Santa Rosa, Zacapa; 100-1400 msnm)",
        "institucion": "ICTA",
        "fecha": "2015-12",
        "url": "https://www.icta.gob.gt/publicaciones/Maiz/Recomendaciones%20tecnicas%20para%20el%20cultivo%20de%20maiz%20en%20el%20oriente%20de%20Guatemala%202015.pdf",
        "consultado": ACCESSED,
        "nota": "Ciclo de ICTA B-5 (3 meses) e ICTA B-7 (4 meses) para lugares con escasez de lluvia; siembra a finales de mayo o inicios de junio.",
    },
    "ICTA_PROGRAMA_MAIZ": {
        "titulo": "Programa de maíz: variedades ICTA B-1, B-5 (ciclo precoz 90 días), B-7TS (tolerante a sequía), B-9ACP, B-15ACP+Zn",
        "institucion": "ICTA",
        "url": "https://www.icta.gob.gt/programademaiz.html",
        "consultado": ACCESSED,
        "nota": "La página no da días a floración ni madurez de ninguna variedad; B-9 y B-15 sin ciclo.",
    },
    "ICTA_FRIJOL_2011": {
        "titulo": "Producción de frijol Phaseolus vulgaris L. (ICTA/FAO), Cuadro 1: características agronómicas de variedades mejoradas",
        "institucion": "ICTA / FAO",
        "fecha": "2011",
        "url": "https://www.icta.gob.gt/publicaciones/Frijol/Produccion%20de%20Frijol%20Phaseolus%20vulgaris%20L%202011.pdf",
        "consultado": ACCESSED,
        "nota": "Ostúa y Santa Gertrudis: días a floración 38-40, días a cosecha 70-75, adaptación 50-1200 msnm, recomendadas para Sur, Oriente y Norte. Leído de la imagen escaneada (p. 4).",
    },
    "ICTA_MEMORIA_2002": {
        "titulo": "Memoria de labores 2002 (floración de ICTA B-7 = 53 d e ICTA B-5 = 48 d en ensayos)",
        "institucion": "ICTA",
        "fecha": "2002",
        "url": "https://www.icta.gob.gt/publicaciones/Memoriasicta/Memoria%20de%20labores%202002.pdf",
        "consultado": "2026-11-15",
        "nota": "Valores registrados en una pasada previa (catalogs/r2/reference/web_sourced_crops.yaml); NO re-verificados en esta pasada (PDF escaneado de muchas páginas).",
    },
    "MAGA_INFORME_6_2025": {
        "titulo": "Informe No. 6 (8 de mayo de 2025): criterio de pentadas para establecer la temporada lluviosa, con datos de INSIVUMEH e ICC",
        "institucion": "MAGA - DIGEGR / CIEA",
        "fecha": "2025-05-08",
        "url": "https://www.maga.gob.gt/download/informe6-25.pdf",
        "consultado": ACCESSED,
        "nota": "Texto leído directamente. Es un criterio operativo de MAGA que usa datos INSIVUMEH/ICC (adaptado de Alfaro, Cid y Enfield, 1999); no es un documento metodológico de INSIVUMEH.",
    },
    "MAGA_EPOCAS": {
        "titulo": "Épocas de siembra y cosecha de cultivos agrícolas de Guatemala",
        "institucion": "MAGA",
        "url": "https://www.maga.gob.gt/download/epocas-siembra-cosecha-agricolas-guatemala.pdf",
        "consultado": "2026-11-15",
        "nota": "Contexto nacional/regional; las fechas de Jocotán de este JSON son provisionales.",
    },
    "USUARIO_SANDBOX": {
        "titulo": "Reglas y umbrales provisionales proporcionados por el equipo del proyecto",
        "institucion": "MILPA RESILIENTE",
        "url": None,
        "consultado": ACCESSED,
        "nota": "Sin cita agronómica; requieren validación MAGA/ICTA.",
    },
}


def stage_rows(crop, variety, durations, kc, dtype, conf, src, assumption):
    rows = []
    kcs = [
        (kc["ini"], kc["ini"]),
        (kc["ini"], kc["mid"]),
        (kc["mid"], kc["mid"]),
        (kc["mid"], kc["end"]),
    ]
    for name, days, (k0, k1) in zip(STAGES, durations, kcs, strict=True):
        rows.append(
            {
                "cultivo": crop,
                "variedad": variety,
                "etapa_fao": name,
                "duracion_dias": days,
                "kc_inicio": k0,
                "kc_fin": k1,
                "kc_tipo": "constante (FAO-56 Tabla 12)"
                if k0 == k1
                else "interpolación lineal entre valores FAO-56",
                "fuente": src,
                "confianza": conf,
                "tipo_dato": dtype,
                "supuesto_aplicado": assumption,
            }
        )
    return rows


def variety(
    name, cycle, flowering, harvest, dtype, conf, src, tolerant, ciclos, notes, conflicts=None
):
    return {
        "nombre": name,
        "ciclo_total_dias": cycle,
        "dias_floracion": flowering,
        "dias_cosecha": harvest,
        "tipo_dato": dtype,
        "confianza": conf,
        "fuentes": src,
        "tolerante_sequia": tolerant,
        "ciclos_documentados": ciclos,
        "notas": notes,
        "valores_en_conflicto": conflicts,
    }


# Traducciones al inglés de los textos mostrados en la interfaz (la fuente en español no cambia).
EN_ASSUMPTIONS = {
    "ICTA B-7": "Cycle of 4 months (ICTA 2015) = 120 d at 30 d/month; stages split with the 20/35/40/30 proportions of FAO-56 Table 11 (maize, 125 d). Kc = FAO-56 Maize (grain) proxy.",
    "ICTA B-5": "Early cycle of 90 d (ICTA programme page; 3 months in ICTA 2015); stages split with FAO-56 Table 11 proportions. Kc = FAO-56 proxy.",
    "NOT_FOUND": "NOT FOUND: ICTA publishes no cycle length or flowering for this variety in the sources consulted. The FAO-56 Table 11 row for grain maize, 125 d (20/35/40/30) is used as a provisional reference; it is not an ICTA measurement.",
    "BEAN": "Days to harvest 70-75 (73 used) and to flowering 38-40 (39 used), ICTA Table 1. Initial+Development = 39 d (end of development assumed to coincide with flowering) split 15:25; Mid+Late = 34 d split 35:20 (FAO-56 Table 11 proportions, dry beans). Kc = FAO-56 Beans, dry proxy.",
}
EN_NOTES = {
    "FAO56": "The maize Kc ini sits in an image of the table: the value 0.30 is the published table value, not read by text extraction; verify against the original.",
    "ICTA_MAIZ_ORIENTE_2015": "Cycle of ICTA B-5 (3 months) and ICTA B-7 (4 months) for places with scarce rain; sow at the end of May or early June.",
    "ICTA_PROGRAMA_MAIZ": "The page gives no days to flowering or maturity for any variety; B-9 and B-15 have no cycle.",
    "ICTA_FRIJOL_2011": "Ostúa and Santa Gertrudis: days to flowering 38-40, days to harvest 70-75, adaptation 50-1200 masl, recommended for South, East and North. Read from the scanned image (p. 4).",
    "ICTA_MEMORIA_2002": "Values recorded in an earlier pass (catalogs/r2/reference/web_sourced_crops.yaml); NOT re-verified in this pass (multi-page scanned PDF).",
    "MAGA_INFORME_6_2025": "Text read directly. It is an operational MAGA criterion using INSIVUMEH/ICC data (adapted from Alfaro, Cid and Enfield, 1999); it is not a methodological document of INSIVUMEH.",
    "MAGA_EPOCAS": "National/regional context; the Jocotán dates in this JSON are provisional.",
    "USUARIO_SANDBOX": "No agronomic citation; requires MAGA/ICTA validation.",
}
EN_GENERAL = [
    "The Kc values are FAO-56 (Table 12) proxies for grain maize and dry beans; there is no Kc measured for ICTA varieties.",
    "FAO-56 Kc values correspond to a sub-humid climate (RHmin ≈ 45 %, u2 ≈ 2 m/s); no climate adjustment was applied because POWER does not provide RHmin.",
    "Stage durations are derived with FAO-56 Table 11 proportions and must be calibrated with local observations.",
    "A date outside the window is a compatibility notice against the configured calendar, not a prohibition.",
]


def add_english(data: dict) -> dict:
    for row in data["parametros_fenologicos"]:
        if row["variedad"] == "ICTA B-7":
            row["supuesto_aplicado_en"] = EN_ASSUMPTIONS["ICTA B-7"]
        elif row["variedad"] == "ICTA B-5":
            row["supuesto_aplicado_en"] = EN_ASSUMPTIONS["ICTA B-5"]
        elif row["cultivo"] == "frijol":
            row["supuesto_aplicado_en"] = EN_ASSUMPTIONS["BEAN"]
        else:
            row["supuesto_aplicado_en"] = EN_ASSUMPTIONS["NOT_FOUND"]
    for key, body in data["fuentes"].items():
        body["nota_en"] = EN_NOTES[key]
    data["supuestos_generales_en"] = EN_GENERAL
    data["estado_validacion_en"] = "Provisional - Pending official MAGA/ICTA validation"
    data["inicio_lluvias"]["diferencias_respecto_al_oficial_en"] = [
        "The criterion comes from a MAGA report that uses INSIVUMEH and ICC data; INSIVUMEH's own methodological procedure was not located.",
        "The wording 'the previous and following pentads must exceed 0.5 mm' is ambiguous: here >0.5 mm is required in the previous pentad and in the two following ones.",
        "It is applied to zonal satellite precipitation, not to station observations.",
    ]
    return data


def build() -> dict:
    kc_maiz = {"ini": 0.30, "mid": 1.20, "end": 0.35}
    kc_frijol = {"ini": 0.40, "mid": 1.15, "end": 0.35}

    b7 = split_days(120, FAO_MAIZE)
    b5 = split_days(90, FAO_MAIZE)
    prox = list(FAO_MAIZE)  # 125 d tal cual (proxy FAO)
    bean = split_days(39, FAO_BEAN[:2]) + split_days(73 - 39, FAO_BEAN[2:])
    assert sum(b7) == 120 and sum(b5) == 90 and sum(prox) == 125 and sum(bean) == 73

    table = []
    table += stage_rows(
        "maiz",
        "ICTA B-7",
        b7,
        kc_maiz,
        "derivado",
        "media-baja",
        ["ICTA_MAIZ_ORIENTE_2015", "FAO56"],
        "Ciclo 4 meses (ICTA 2015) = 120 d con 30 d/mes; etapas repartidas con las proporciones 20/35/40/30 de FAO-56 Tabla 11 (maíz, 125 d). Kc = proxy FAO-56 Maize (grain).",
    )
    table += stage_rows(
        "maiz",
        "ICTA B-5",
        b5,
        kc_maiz,
        "derivado",
        "media-baja",
        ["ICTA_PROGRAMA_MAIZ", "ICTA_MAIZ_ORIENTE_2015", "FAO56"],
        "Ciclo precoz de 90 d (ICTA, página del programa; 3 meses en ICTA 2015); etapas con proporciones FAO-56 Tabla 11. Kc = proxy FAO-56.",
    )
    for v in ("ICTA B-9", "ICTA B-15"):
        table += stage_rows(
            "maiz",
            v,
            prox,
            kc_maiz,
            "proxy FAO-56",
            "baja",
            ["FAO56"],
            "NO ENCONTRADO: ICTA no publica ciclo ni floración de esta variedad en las fuentes consultadas. Se usa la fila FAO-56 Tabla 11 maíz grano 125 d (20/35/40/30) como referencia provisional; no es una medición de ICTA.",
        )
    for v in ("ICTA Ostúa", "ICTA Santa Gertrudis"):
        table += stage_rows(
            "frijol",
            v,
            bean,
            kc_frijol,
            "derivado",
            "media",
            ["ICTA_FRIJOL_2011", "FAO56"],
            "Días a cosecha 70-75 (se usa 73) y a floración 38-40 (se usa 39), ICTA Cuadro 1. Inicial+Desarrollo = 39 d (se asume que el fin del desarrollo coincide con la floración) repartidos 15:25; Media+Final = 34 d repartidos 35:20 (proporciones FAO-56 Tabla 11, frijol seco). Kc = proxy FAO-56 Beans, dry.",
        )

    maiz_vars = [
        variety(
            "ICTA B-7",
            120,
            53,
            None,
            "ciclo derivado de '4 meses'; floración encontrada (cita secundaria)",
            "media-baja",
            ["ICTA_MAIZ_ORIENTE_2015", "ICTA_PROGRAMA_MAIZ", "ICTA_MEMORIA_2002"],
            True,
            {
                "primera": "documentado: siembra a finales de mayo o inicios de junio (ICTA 2015)",
                "postrera": "no documentado en las fuentes consultadas",
            },
            "B-7TS: 'tolerante a sequía' según ICTA (sin nivel cuantitativo).",
            {
                "ciclo_dias": {
                    "ICTA guía general (registro previo)": 95,
                    "ICTA Memoria 2002, días a cosecha (registro previo)": 110,
                    "ICTA 2015 oriente (4 meses)": 120,
                }
            },
        ),
        variety(
            "ICTA B-5",
            90,
            48,
            None,
            "encontrado (ciclo 90 d); floración encontrada (cita secundaria)",
            "media",
            ["ICTA_PROGRAMA_MAIZ", "ICTA_MAIZ_ORIENTE_2015", "ICTA_MEMORIA_2002"],
            None,
            {
                "primera": "documentado: siembra a finales de mayo o inicios de junio (ICTA 2015)",
                "postrera": "no documentado en las fuentes consultadas",
            },
            "ICTA 2015: ciclo de tres meses para lugares con escasez de lluvia.",
        ),
        variety(
            "ICTA B-9",
            None,
            None,
            None,
            "NO ENCONTRADO",
            "baja",
            ["ICTA_PROGRAMA_MAIZ"],
            None,
            {"primera": "no documentado", "postrera": "no documentado"},
            "B-9ACP: alta calidad de proteína; sin ciclo publicado en las fuentes consultadas.",
        ),
        variety(
            "ICTA B-15",
            None,
            None,
            None,
            "NO ENCONTRADO",
            "baja",
            ["ICTA_PROGRAMA_MAIZ"],
            None,
            {"primera": "no documentado", "postrera": "no documentado"},
            "B-15ACP+Zn: biofortificada con zinc y proteína; sin ciclo publicado.",
        ),
    ]
    frijol_vars = [
        variety(
            n,
            73,
            39,
            73,
            "encontrado (rangos 38-40 y 70-75); valores centrales derivados",
            "media",
            ["ICTA_FRIJOL_2011"],
            None,
            {"primera": "no verificado en esta pasada", "postrera": "no verificado en esta pasada"},
            "ICTA Cuadro 1: floración 38-40 d, cosecha 70-75 d, rendimiento 20-29 qq/mz, adaptación 50-1200 msnm; recomendada para Sur, Oriente y Norte.",
        )
        for n in ("ICTA Ostúa", "ICTA Santa Gertrudis")
    ]

    return add_english(
        {
            "version": "2.0.0",
            "status": "sandbox",
            "estado_validacion": "Provisional - Pendiente validación oficial MAGA/ICTA",
            "zona_piloto": {
                "nombre": "Jocotán",
                "departamento": "Chiquimula",
                "pais": "Guatemala",
                "zona_datos": "camotan_jocotan",
            },
            "ventanas_siembra": {
                "primera": {
                    "inicio": "05-01",
                    "fin": "06-30",
                    "estado": "Pending validation - Provisional",
                    "fuentes": ["MAGA_EPOCAS", "USUARIO_SANDBOX"],
                },
                "postrera": {
                    "inicio": "08-20",
                    "fin": "09-30",
                    "estado": "Pending validation - Provisional",
                    "fuentes": ["MAGA_EPOCAS", "USUARIO_SANDBOX"],
                },
            },
            "cultivos": {
                "maiz": {
                    "nombre": "Maíz",
                    "variedades": [v["nombre"] for v in maiz_vars],
                    "kc_etapa_media": 1.20,
                    "kc_fao56": {
                        **kc_maiz,
                        "nota": "Kc end 0.35 = cosecha tras secado completo en campo; FAO-56 da 0.60 si se cosecha con humedad alta de grano.",
                    },
                    "umbrales_hidricos": {
                        "dias_secos_consecutivos_riesgo": 10,
                        "lluvia_minima_mm_dia": 1.0,
                        "lluvia_minima_15_dias_mm": 20.0,
                    },
                    "umbral_basis": "USUARIO_SANDBOX",
                },
                "frijol": {
                    "nombre": "Frijol",
                    "variedades": [v["nombre"] for v in frijol_vars],
                    "kc_etapa_media": 1.15,
                    "kc_fao56": {
                        **kc_frijol,
                        "nota": "FAO-56 Beans, dry; la nota 2 indica Kc mid hasta 1.20 para variedades trepadoras de 1.5-2 m.",
                    },
                    "umbrales_hidricos": {
                        "dias_secos_consecutivos_riesgo": 7,
                        "lluvia_minima_mm_dia": 1.0,
                    },
                    "umbral_basis": "USUARIO_SANDBOX",
                },
            },
            "variedades": {"maiz": maiz_vars, "frijol": frijol_vars},
            "parametros_fenologicos": table,
            "temperatura_siembra": {
                "media_min_c": 22.0,
                "media_max_c": 32.0,
                "nota": "Regla sandbox del piloto; sin cita agronómica.",
            },
            "inicio_lluvias": {
                "metodo": "pentadas",
                "pentada_dias": 5,
                "acumulado_minimo_mm": 25.0,
                "persistencia": {
                    "modo": "al_menos_una_de_las_siguientes",
                    "pentadas_siguientes": 2,
                    "modos_disponibles": ["al_menos_una_de_las_siguientes", "ambas_siguientes"],
                },
                "continuidad_minima_mm": 0.5,
                "busqueda": {"inicio_md": "04-01", "fin_md": "07-31"},
                "dias_minimos_validos_por_pentada": 5,
                "fuente_criterio": "MAGA_INFORME_6_2025",
                "es_metodo_oficial_insivumeh": False,
                "estado": "Escenario Sandbox - No usar para decisiones operativas",
                "diferencias_respecto_al_oficial": [
                    "El criterio proviene de un informe de MAGA que usa datos de INSIVUMEH e ICC; no se localizó el procedimiento metodológico propio de INSIVUMEH.",
                    "La redacción 'las péntadas anteriores y posteriores presenten más de 0.5 mm' es ambigua: aquí se exige >0.5 mm en la pentada previa y en las dos siguientes.",
                    "Se aplica a precipitación satelital zonal, no a observaciones de estación.",
                ],
                "retraso_adaptacion": {"umbral_retraso_dias": 15},
            },
            "estacion_local": {
                "nombre": "INSIVUMEH - Estación Camotán",
                "archivo_por_defecto": "data/estaciones/camotan_insivumeh.csv",
                "columnas": ["fecha", "precipitacion_mm"],
                "unidades": "mm/día (suma diaria), resolución temporal diaria",
                "min_observaciones_nivel_b": 365,
                "min_observaciones_correlacion": 30,
                "estado_inicial": "Nivel C - Pendiente",
            },
            "climate_thresholds": {
                "rainfall_first_15_days_min_mm": 20.0,
                "rainfall_window_days": 15,
                "canicula_daily_rain_below_mm": 1.0,
                "canicula_max_consecutive_dry_days": 10,
                "temperature_mean_min_c": 22.0,
                "temperature_mean_max_c": 32.0,
            },
            "climate_data": {
                "daily_dataset": "curated/camotan_jocotan/daily.parquet",
                "precipitation_column": "precip_mm",
                "satellite_precipitation_column": "precip_imerg_mm",
                "precipitation_method": "IMERG primary with POWER fallback as curated by R1",
                "temperature_source": "NASA POWER daily",
                "coverage_start": "2001-01-01",
                "coverage_end": "2025-12-31",
                "spatial_scope": "zonal estimate, not parcel-specific and not a weather forecast",
            },
            "fuentes": SOURCES,
            "supuestos_generales": [
                "Los Kc son proxies FAO-56 (Tabla 12) para maíz grano y frijol seco; no hay Kc medido por variedad ICTA.",
                "Los Kc de FAO-56 corresponden a clima subhúmedo (HRmin ≈ 45 %, u2 ≈ 2 m/s); no se aplicó ajuste climático porque POWER no entrega HRmin.",
                "Las duraciones de etapas son derivadas con proporciones FAO-56 Tabla 11; deben calibrarse con observaciones locales.",
                "Una fecha fuera de la ventana es una advertencia de compatibilidad con el calendario configurado, no una prohibición.",
            ],
        }
    )


if __name__ == "__main__":
    data = build()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "regions/reglas_agronomicas_jocotan.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"escrito {out} ({len(data['parametros_fenologicos'])} filas de etapas)")
