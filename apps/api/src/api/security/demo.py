"""Alcance de la sesión pública de demostración.

La sesión demo es un token real (firmado, con vida acotada) de una cuenta sin contraseña utilizable y
sin parcelas ni agricultores asociados: RLS ya le oculta todo dato privado. Además solo puede llamar a
las operaciones listadas aquí (lectura de contexto, resultados y catálogo; crear corridas de zona,
escenarios, rankings e informes). Todo lo demás (parcelas, suelo, borrados, administración) responde 403.
"""

from __future__ import annotations

import re

_READ = re.compile(r"^/v1/(zones|runs|catalog|reports|jobs|provenance|auth/me)(/|$)")
_WRITE = (
    re.compile(r"^/v1/zones/[0-9a-fA-F-]{36}/runs$"),
    re.compile(r"^/v1/runs/[0-9a-fA-F-]{36}/(scenarios|rank)$"),
    re.compile(r"^/v1/reports$"),
)


def demo_allows(method: str, path: str) -> bool:
    if method in {"GET", "HEAD", "OPTIONS"}:
        return bool(_READ.match(path))
    if method == "POST":
        return any(p.match(path) for p in _WRITE)
    return False
