"""DTO de la estimación sandbox del inicio de lluvias y del estado de validación con la estación Camotán."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class PentadOut(BaseModel):
    pentada: int
    inicio: date
    fin: date
    precipitacion_mm: float | None = Field(
        description="null si algún día de la pentada no tiene dato (nunca se rellena con cero)"
    )
    dias_validos: int
    dias_totales: int
    completa: bool


class AdaptationDelayOut(BaseModel):
    dias_diferencia: int | None
    advertencias: list[str]
    conclusion: str
    mensaje: str
    nota: str


class RainySeasonOnsetResponse(BaseModel):
    fecha_estimada_inicio: date | None
    metodo: str
    precipitacion_pentadas: list[PentadOut]
    estado: str
    limitaciones: list[str]
    fuente_precipitacion: str
    criterio: dict[str, Any]
    anio: int | None
    resultado: str = Field(description="detectado | no_detectado | datos_insuficientes")
    entradas: dict[str, Any]
    retraso_adaptacion: AdaptationDelayOut | None = None
    aviso: str
    es_metodo_oficial_insivumeh: bool = False


class StationValidationResponse(BaseModel):
    estado_validacion: str
    mensaje: str
    metricas: dict[str, Any] | None
    fuente_sugerida: str
    producto_satelital: str
    carga_habilitada: bool = Field(
        description="false: la interfaz no procesa archivos; el CSV lo coloca el operador en el servidor"
    )
    aviso: str
    filas: dict[str, int] | None = None
    es_ejemplo_ficticio: bool = False


class PlantingOptionVariety(BaseModel):
    nombre: str
    ciclo_total_dias: int | None
    tipo_dato: str
    confianza: str
    tolerante_sequia: bool | None


class PlantingOptionCrop(BaseModel):
    clave: str
    nombre: str
    variedades: list[PlantingOptionVariety]


class PlantingOptionCycle(BaseModel):
    ciclo: str
    inicio: str = Field(description="MM-DD")
    fin: str = Field(description="MM-DD")
    estado: str


class PlantingOptionsResponse(BaseModel):
    """Opciones del formulario de siembra: salen del JSON de reglas, no del código del frontend."""

    cultivos: list[PlantingOptionCrop]
    ciclos: list[PlantingOptionCycle]
    estado_validacion: str
    aviso: str
