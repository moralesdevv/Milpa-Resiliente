"""Suelo: estado por propiedad (disponibilidad) y contexto de la parcela (apartado 20).

La disponibilidad (``PropertyStatus``) es independiente de la aplicabilidad y del
resultado del VoI. Una propiedad sin valor nunca resulta ``medido`` (T-P10).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..enums import Evidence, PropertyStatus, Provenance

_STATUS_EVIDENCE = {
    PropertyStatus.MEDIDO: Evidence.A,
    PropertyStatus.ESTIMADO: Evidence.C,
    PropertyStatus.DECLARADO: Evidence.C,
    PropertyStatus.DESACTUALIZADO: Evidence.C,
    PropertyStatus.NO_REPRESENTATIVO: Evidence.C,
}


@dataclass(frozen=True)
class PropertyValue:
    code: str
    status: PropertyStatus
    value: float | None = None
    method: str | None = None
    depth_cm: tuple[int, int] | None = None
    sampled_at: str | None = None
    p05: float | None = None  # producto espacial (estimado)
    p95: float | None = None
    representativeness: str | None = None
    age_years: float | None = None
    max_age_years: int | None = None

    def __post_init__(self) -> None:
        st = PropertyStatus(self.status)
        if self.value is None and st in (PropertyStatus.MEDIDO, PropertyStatus.ESTIMADO, PropertyStatus.DECLARADO):
            object.__setattr__(self, "status", PropertyStatus.DESCONOCIDO)
        if st is PropertyStatus.MEDIDO and not self.method:
            # sin método no se acepta el dato medido (apartado 21)
            object.__setattr__(self, "status", PropertyStatus.DESCONOCIDO)
            object.__setattr__(self, "value", None)
        if st is PropertyStatus.MEDIDO and self.age_years is not None and self.max_age_years is not None \
                and self.age_years > self.max_age_years:
            object.__setattr__(self, "status", PropertyStatus.DESACTUALIZADO)

    @property
    def evidence(self) -> Evidence | None:
        return _STATUS_EVIDENCE.get(PropertyStatus(self.status))

    @property
    def provenance(self) -> Provenance:
        return {
            PropertyStatus.MEDIDO: Provenance.MEDIDO, PropertyStatus.ESTIMADO: Provenance.ESTIMADO,
            PropertyStatus.DECLARADO: Provenance.DECLARADO,
        }.get(PropertyStatus(self.status), Provenance.DESCONOCIDO)


@dataclass(frozen=True)
class InitialCondition:
    dr0_mm: float
    basis: str  # 'supuesto declarado' | 'medición'


@dataclass(frozen=True)
class SoilContext:
    properties: Mapping[str, PropertyValue] = field(default_factory=dict)
    initial_condition: InitialCondition | None = None
    previous_crop_family: str | None = None  # historial declarado

    def property(self, code: str) -> PropertyValue:
        return self.properties.get(code) or PropertyValue(code, PropertyStatus.DESCONOCIDO)

    property_status = property


def from_csv_row(row: Mapping[str, object], method_by_prop: Mapping[str, str] | None = None) -> SoilContext:
    """Una fila de CSV con pH y sin materia orgánica → MO desconocido (T-P10)."""
    props = {}
    for code in ("ph", "om_pct", "awc_mm_m", "effective_depth", "sand_pct", "clay_pct"):
        v = row.get(code)
        if v is None or (isinstance(v, float) and v != v) or v == "":
            props[code] = PropertyValue(code, PropertyStatus.DESCONOCIDO)
        else:
            props[code] = PropertyValue(code, PropertyStatus.MEDIDO, float(v), (method_by_prop or {}).get(code, "lab"))
    return SoilContext(props)
