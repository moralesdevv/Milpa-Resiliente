"""Convenciones de unidades: sufijo en el nombre de cada campo.

_mm (mm), _c (°C), _ms (m/s), _mj_m2 (MJ m-2 día-1), _kpa, _pct, _m.
"""
UNIT_BY_SUFFIX = {
    "_mm": "mm",
    "_c": "°C",
    "_ms": "m/s",
    "_mj_m2": "MJ m-2 d-1",
    "_kpa": "kPa",
    "_pct": "%",
    "_m": "m",
    "_kg_ha": "kg/ha",
    "_kcal_ha": "kcal/ha",
}


def unit_for(field_name: str) -> str | None:
    for suf, unit in sorted(UNIT_BY_SUFFIX.items(), key=lambda kv: -len(kv[0])):
        if field_name.endswith(suf):
            return unit
    return None
