"""Revisión de la fecha de siembra para Jocotán: lee las señales hídricas (del usuario o de la serie histórica
zonal) y delega la evaluación en ``api.agronomy.validation`` con parámetros de ``reglas_agronomicas_jocotan.json``."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import pandas as pd

from api.agronomy.climate import load_daily
from api.agronomy.i18n import t
from api.agronomy.rules import Rules, RulesError, load_rules
from api.agronomy.validation import validar_siembra
from api.errors import NotFound, ServiceUnavailable, ValidationFailed
from api.repositories.farms import ZoneRepository
from api.schemas.parcels import (
    PlantingValidationRequest,
    PlantingValidationResponse,
)
from api.services.access import AccessPolicy
from api.services.context import ServiceContext

ALLOWED_ZONES = {"camotan_jocotan", "jocotan"}


def load_rules_or_503(ctx: ServiceContext) -> Rules:
    try:
        return load_rules(ctx.settings.planting_rules_path)
    except RulesError as exc:
        raise ServiceUnavailable(
            "La configuración agronómica de Jocotán no está disponible; el resto de la aplicación sigue funcionando.",
            hint=str(exc),
        ) from exc


class PlantingValidationService:
    def __init__(self, ctx: ServiceContext) -> None:
        self.ctx = ctx
        self.access = AccessPolicy(ctx)
        self.zones = ZoneRepository(ctx.session)

    def validate(
        self, parcel_id: UUID, request: PlantingValidationRequest
    ) -> PlantingValidationResponse:
        parcel = self.access.parcel(self.ctx.user, parcel_id)
        return self.validate_zone(parcel.zone_id, request)

    def validate_zone(
        self, zone_id: UUID, request: PlantingValidationRequest
    ) -> PlantingValidationResponse:
        zone = self.zones.get(zone_id)
        if zone is None:
            raise NotFound("Parcela no encontrada")
        if zone.name.casefold() not in ALLOWED_ZONES:
            raise ValidationFailed(
                "La validación MAGA/ZARC disponible está configurada solo para Jocotán."
            )
        rules = load_rules_or_503(self.ctx)
        daily = load_daily(self.ctx.store, str(rules.raw["climate_data"]["daily_dataset"]))
        return self._evaluate(request, rules, daily)

    def _evaluate(
        self, request: PlantingValidationRequest, rules: Rules, daily: pd.DataFrame
    ) -> PlantingValidationResponse:
        day = request.fecha_siembra
        ciclo = request.ciclo or self._infer_cycle(rules, day)
        crop_key = rules.crop_key(request.cultivo)
        limits = rules.crop(crop_key)["umbrales_hidricos"] if crop_key else {}
        legacy = rules.raw["climate_thresholds"]
        days = int(legacy["rainfall_window_days"])
        dry_below = float(
            limits.get("lluvia_minima_mm_dia", legacy["canicula_daily_rain_below_mm"])
        )

        period = pd.date_range(pd.Timestamp(day), periods=days, freq="D")
        rain = pd.to_numeric(daily.reindex(period)["precip_mm"], errors="coerce")
        available = int(rain.notna().sum())
        complete = available == days
        derived_total = float(rain.sum()) if complete else None
        derived_streak = max_dry_streak(rain.tolist(), dry_below) if complete else None
        temperature = planting_day_temperature(daily, pd.Timestamp(day))

        declared = request.dias_secos_recientes is not None or request.lluvia_15_dias_mm is not None
        dry_days = (
            request.dias_secos_recientes
            if request.dias_secos_recientes is not None
            else derived_streak
        )
        rain_15 = (
            request.lluvia_15_dias_mm if request.lluvia_15_dias_mm is not None else derived_total
        )

        result = validar_siembra(
            rules,
            request.cultivo,
            request.variedad,
            day,
            ciclo,
            dry_days,
            rain_15,
            temperature,
            request.idioma,
        )
        advertencias: list[str] = list(result["advertencias"])
        enough = True
        if not complete and not declared:
            enough = False
            advertencias.append(
                t("insufficient_zone_data", request.idioma, available=available, days=days)
            )
        if temperature is None:
            advertencias.append(t("no_temperature", request.idioma))

        start, end = daily.index.min(), daily.index.max()
        sources = {
            str(k): int(v)
            for k, v in daily.reindex(period)["precip_source"].value_counts(dropna=True).items()
        }
        return PlantingValidationResponse(
            es_valido=bool(result["es_valido"]) and enough,
            datos_suficientes=enough,
            alertas=list(result["alertas"]),
            advertencias=advertencias,
            recomendacion=recommendation(result, enough, request.idioma),
            fecha_en_ventana=result["fecha_en_ventana"],
            senal_sequia=bool(result["senal_sequia"]),
            fecha_siembra=day,
            cultivo=str(result["cultivo"]),
            variedad=str(result["variedad"]),
            ciclo=str(result["ciclo"]),
            precipitacion_15_dias_mm=rain_15,
            dias_lluvia_disponibles=available,
            temperatura_media_fecha_c=temperature,
            racha_seca_maxima_dias=dry_days,
            origen_senales_hidricas=t(
                "origin_declared" if declared else "origin_zonal", request.idioma
            ),
            fuentes_precipitacion=sources,
            cobertura_climatica={
                "desde": start.date().isoformat() if pd.notna(start) else "",
                "hasta": end.date().isoformat() if pd.notna(end) else "",
            },
            kc_etapa_media=result["kc_etapa_media"],
            parametros_fenologicos=result["parametros_fenologicos"],
            umbrales_aplicados=list(result["umbrales_aplicados"]),
            estado_validacion=str(result["estado_validacion"]),
            fuentes=list(result["fuentes"]),
            supuestos=list(result["supuestos"]),
            alcance=(
                "Estimación de clima zonal de Jocotán; no usa observación ni pronóstico específico de la parcela. "
                "Lluvia: IMERG con respaldo POWER; temperatura: POWER. Los datos que usted declara tienen prioridad sobre la serie."
            ),
            estado_reglas=str(rules.status),
        )

    @staticmethod
    def _infer_cycle(rules: Rules, day: date) -> str:
        md = day.strftime("%m-%d")
        for name in rules.cycles:
            window = rules.window(name)
            if window and str(window["inicio"]) <= md <= str(window["fin"]):
                return name
        return rules.cycles[0]


def recommendation(result: dict[str, Any], enough: bool, lang: str = "es") -> str:
    if result["senal_sequia"]:
        return t("rec_drought", lang)
    if enough and not result["alertas"]:
        return t("rec_ok", lang)
    if not enough:
        return t("rec_insufficient", lang)
    return t("rec_review", lang)


def planting_day_temperature(daily: pd.DataFrame, day: pd.Timestamp) -> float | None:
    if day not in daily.index:
        return None
    row = daily.loc[day]
    tmax = pd.to_numeric(row["tmax_c"], errors="coerce")
    tmin = pd.to_numeric(row["tmin_c"], errors="coerce")
    if pd.isna(tmax) or pd.isna(tmin):
        return None
    return float((tmax + tmin) / 2)


def max_dry_streak(values: list[Any], threshold: float) -> int:
    longest = current = 0
    for value in values:
        if value is not None and pd.notna(value) and float(value) < threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
