"""Servicios de solo lectura: inicio de lluvias SANDBOX y estado de validación contra la estación Camotán."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID

import pandas as pd

from api.agronomy.climate import load_daily
from api.agronomy.onset import detectar_inicio_lluvias, evaluar_retraso_adaptacion
from api.agronomy.rules import Rules
from api.agronomy.station import validar_con_estacion_local
from api.errors import NotFound, ValidationFailed
from api.repositories.farms import ZoneRepository
from api.schemas.agronomy import (
    PlantingOptionCrop,
    PlantingOptionCycle,
    PlantingOptionsResponse,
    PlantingOptionVariety,
    RainySeasonOnsetResponse,
    StationValidationResponse,
)
from api.services.context import ServiceContext
from api.services.planting import ALLOWED_ZONES, load_rules_or_503

SANDBOX_NOTICE = (
    "This estimated onset of the rainy season uses a configurable pentad-based rainfall method. It does not replace "
    "official INSIVUMEH bulletins and must not be used as the sole basis for planting decisions."
)
STATION_NOTICE = (
    "Satellite precipitation data have not yet been validated against the Camotán meteorological station. "
    "Historical station data are pending from INSIVUMEH."
)
SATELLITE_PRODUCT = "GPM IMERG Final V07B (días con dato IMERG; no incluye el respaldo POWER)"


PLANTING_NOTICE = "Planting dates and agronomic thresholds are provisional references pending official validation for Jocotán by MAGA/ICTA."


class AgronomyService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.zones = ZoneRepository(ctx.session)

    def _zone_daily(self, zone_id: UUID) -> tuple[Rules, pd.DataFrame]:
        zone = self.zones.get(zone_id)
        if zone is None:
            raise NotFound("Zona no encontrada")
        if zone.name.casefold() not in ALLOWED_ZONES:
            raise ValidationFailed(
                "Esta estimación está configurada solo para la zona piloto de Jocotán."
            )
        rules = load_rules_or_503(self.ctx)
        return rules, load_daily(self.ctx.store, str(rules.raw["climate_data"]["daily_dataset"]))

    def rainy_season_onset(
        self, zone_id: UUID, anio: int | None, fecha_siembra: date | None, idioma: str = "es"
    ) -> RainySeasonOnsetResponse:
        rules, daily = self._zone_daily(zone_id)
        config = rules.onset
        year = anio if anio is not None else int(daily.index.max().year)
        rain = pd.to_numeric(daily["precip_mm"], errors="coerce")
        window = daily.loc[(daily.index >= f"{year}-01-01") & (daily.index <= f"{year}-12-31")]
        counts = window["precip_source"].value_counts(dropna=True)
        source = (
            "; ".join(f"{k}: {int(v)} días" for k, v in counts.items()) or "sin datos en el año"
        )
        result = detectar_inicio_lluvias(
            rain, config, year, f"Serie diaria curada de la zona ({source})", idioma
        )
        delay = None
        if fecha_siembra is not None:
            delay = evaluar_retraso_adaptacion(
                result["fecha_estimada_inicio"],
                fecha_siembra,
                int(config.get("retraso_adaptacion", {}).get("umbral_retraso_dias", 15)),
                idioma,
            )
        return RainySeasonOnsetResponse(
            **result,
            retraso_adaptacion=delay,
            aviso=SANDBOX_NOTICE,
            es_metodo_oficial_insivumeh=bool(config.get("es_metodo_oficial_insivumeh", False)),
        )

    def station_validation(self, zone_id: UUID, idioma: str = "es") -> StationValidationResponse:
        rules, daily = self._zone_daily(zone_id)
        config = rules.station
        satellite = (
            pd.to_numeric(daily["precip_imerg_mm"], errors="coerce")
            if "precip_imerg_mm" in daily
            else None
        )
        path: Path | None = self.ctx.settings.station_csv_path
        csv = path if path is not None and path.is_file() else None
        result = validar_con_estacion_local(satellite, csv, config, SATELLITE_PRODUCT, idioma)
        return StationValidationResponse(
            estado_validacion=result["estado_validacion"],
            mensaje=result["mensaje"],
            metricas=result["metricas"],
            fuente_sugerida=result["fuente_sugerida"],
            producto_satelital=SATELLITE_PRODUCT,
            carga_habilitada=False,
            aviso=STATION_NOTICE,
            filas=result.get("filas"),
            es_ejemplo_ficticio=bool(result.get("es_ejemplo_ficticio", False)),
        )

    def planting_options(self, zone_id: UUID) -> PlantingOptionsResponse:
        zone = self.zones.get(zone_id)
        if zone is None:
            raise NotFound("Zona no encontrada")
        if zone.name.casefold() not in ALLOWED_ZONES:
            raise ValidationFailed(
                "Estas opciones están configuradas solo para la zona piloto de Jocotán."
            )
        rules = load_rules_or_503(self.ctx)
        crops = [
            PlantingOptionCrop(
                clave=key,
                nombre=str(body["nombre"]),
                variedades=[
                    PlantingOptionVariety(
                        nombre=str(v["nombre"]),
                        ciclo_total_dias=v.get("ciclo_total_dias"),
                        tipo_dato=str(v["tipo_dato"]),
                        confianza=str(v["confianza"]),
                        tolerante_sequia=v.get("tolerante_sequia"),
                    )
                    for v in rules.varieties(key)
                ],
            )
            for key, body in rules.raw["cultivos"].items()
        ]
        cycles = [
            PlantingOptionCycle(
                ciclo=name,
                inicio=str(w["inicio"]),
                fin=str(w["fin"]),
                estado=str(w.get("estado", "")),
            )
            for name in rules.cycles
            if (w := rules.window(name))
        ]
        return PlantingOptionsResponse(
            cultivos=crops,
            ciclos=cycles,
            estado_validacion=rules.estado_validacion,
            aviso=PLANTING_NOTICE,
        )
