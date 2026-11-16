"""Carga y consulta de ``reglas_agronomicas_jocotan.json``, la fuente central de parámetros agronómicos.

Un archivo ausente o mal formado produce ``RulesError`` (error controlado): el servicio lo traduce a 503 para
ese endpoint y el resto de la aplicación sigue funcionando. Nada de lo que hay aquí calcula: solo lee.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MD_LEN = 5  # "MM-DD"


class RulesError(Exception):
    """El archivo de reglas falta, no es JSON o no tiene la estructura esperada."""


def norm(text: str) -> str:
    """Compara nombres sin tildes ni mayúsculas ('Maíz' == 'maiz')."""
    decomposed = unicodedata.normalize("NFKD", text.strip())
    return str("".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold())


def _need(mapping: Any, key: str, kind: type | tuple[type, ...], where: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise RulesError(f"Falta '{key}' en {where}")
    value = mapping[key]
    if not isinstance(value, kind):
        raise RulesError(f"'{where}.{key}' tiene un tipo inválido")
    return value


def _check_md(value: Any, where: str) -> str:
    ok = (
        isinstance(value, str)
        and len(value) == MD_LEN
        and value[2] == "-"
        and value[:2].isdigit()
        and value[3:].isdigit()
    )
    if not ok:
        raise RulesError(f"{where} debe tener formato MM-DD")
    month, day = int(value[:2]), int(value[3:])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise RulesError(f"{where} no es una fecha válida")
    return str(value)


@dataclass(frozen=True)
class Rules:
    raw: dict[str, Any]

    # -- identidad ---------------------------------------------------------------------------
    @property
    def estado_validacion(self) -> str:
        return str(self.raw["estado_validacion"])

    def estado_for(self, lang: str) -> str:
        if lang == "en" and self.raw.get("estado_validacion_en"):
            return str(self.raw["estado_validacion_en"])
        return self.estado_validacion

    @property
    def status(self) -> str:
        return str(self.raw.get("status", "sandbox"))

    @property
    def supuestos(self) -> list[str]:
        return [str(s) for s in self.raw.get("supuestos_generales", [])]

    # -- cultivos y variedades ----------------------------------------------------------------
    def crop_key(self, cultivo: str) -> str | None:
        for key, body in self.raw["cultivos"].items():
            if norm(key) == norm(cultivo) or norm(str(body.get("nombre", ""))) == norm(cultivo):
                return str(key)
        return None

    def crop(self, key: str) -> dict[str, Any]:
        return dict(self.raw["cultivos"][key])

    def varieties(self, key: str) -> list[dict[str, Any]]:
        return [dict(v) for v in self.raw["variedades"].get(key, [])]

    def variety(self, key: str, name: str) -> dict[str, Any] | None:
        for item in self.raw["variedades"].get(key, []):
            if norm(str(item["nombre"])) == norm(name):
                return dict(item)
        return None

    def phenology(self, key: str, variety_name: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.raw["parametros_fenologicos"]
            if row["cultivo"] == key and norm(str(row["variedad"])) == norm(variety_name)
        ]

    # -- ventanas ------------------------------------------------------------------------------
    @property
    def cycles(self) -> list[str]:
        return list(self.raw["ventanas_siembra"])

    def window(self, ciclo: str) -> dict[str, Any] | None:
        for key, body in self.raw["ventanas_siembra"].items():
            if norm(key) == norm(ciclo):
                return {"ciclo": key, **body}
        return None

    # -- fuentes -------------------------------------------------------------------------------
    def sources(self, ids: list[str], lang: str = "es") -> list[dict[str, Any]]:
        catalog = self.raw.get("fuentes", {})
        out: list[dict[str, Any]] = []
        for i in ids:
            if i not in catalog:
                continue
            item = {"id": i, **catalog[i]}
            if lang == "en" and item.get("nota_en"):
                item["nota"] = item["nota_en"]
            out.append(item)
        return out

    def supuestos_for(self, lang: str) -> list[str]:
        key = "supuestos_generales_en" if lang == "en" else "supuestos_generales"
        return [str(s) for s in (self.raw.get(key) or self.raw.get("supuestos_generales", []))]

    @property
    def onset(self) -> dict[str, Any]:
        return dict(self.raw["inicio_lluvias"])

    @property
    def station(self) -> dict[str, Any]:
        return dict(self.raw["estacion_local"])


def validate_structure(raw: Any) -> Rules:
    if not isinstance(raw, dict):
        raise RulesError("La raíz del archivo de reglas debe ser un objeto JSON")
    _need(raw, "estado_validacion", str, "raíz")
    windows = _need(raw, "ventanas_siembra", dict, "raíz")
    if not windows:
        raise RulesError("'ventanas_siembra' no define ningún ciclo")
    for name, body in windows.items():
        _check_md(
            _need(body, "inicio", str, f"ventanas_siembra.{name}"),
            f"ventanas_siembra.{name}.inicio",
        )
        _check_md(
            _need(body, "fin", str, f"ventanas_siembra.{name}"), f"ventanas_siembra.{name}.fin"
        )
    crops = _need(raw, "cultivos", dict, "raíz")
    for name, body in crops.items():
        _need(body, "variedades", list, f"cultivos.{name}")
        _need(body, "kc_etapa_media", (int, float), f"cultivos.{name}")
        _need(body, "umbrales_hidricos", dict, f"cultivos.{name}")
    _need(raw, "variedades", dict, "raíz")
    _need(raw, "parametros_fenologicos", list, "raíz")
    onset = _need(raw, "inicio_lluvias", dict, "raíz")
    _need(onset, "acumulado_minimo_mm", (int, float), "inicio_lluvias")
    _need(raw, "estacion_local", dict, "raíz")
    return Rules(raw)


def load_rules(path: Path) -> Rules:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RulesError(f"No se pudo leer el archivo de reglas agronómicas ({path.name})") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RulesError(
            f"El archivo de reglas agronómicas no es JSON válido (línea {exc.lineno})"
        ) from exc
    return validate_structure(raw)
