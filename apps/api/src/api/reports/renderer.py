"""Renderizado Jinja2 + WeasyPrint con recursos restringidos (spec R3 §15.5, README §22).

Controles anti-SSRF / lectura de archivos:
  * La plantilla y el CSS de impresión se cargan del directorio de plantillas y el CSS se INCRUSTA
    en el HTML: el PDF no necesita ninguna recuperación de recursos.
  * ``url_fetcher`` solo permite esquema ``data:``; cualquier otro (http, https, file, ftp…) se
    deniega y se registra (para pruebas y diagnóstico), sin tocar red ni disco.
  * ``base_url=None``: las URL relativas no se resuelven contra el sistema de archivos.
  * Jinja2 en entorno *sandbox* con autoescape y variables indefinidas estrictas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader, StrictUndefined, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup

from api.reports.contract import TEMPLATE_VERSION, ReportInput
from api.security.privacy import find_sensitive

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
TEMPLATE_NAME = "report_provisional.html.j2"
CSS_NAME = "report_print.css"

DISCLAIMER_ES = (
    "Este documento no constituye una recomendación automática. Es un apoyo a la decisión "
    "cuya interpretación corresponde a la persona técnica y a la familia agricultora."
)
DISCLAIMER_EN = (
    "This document is not an automatic recommendation. It supports a decision whose "
    "interpretation rests with the technician and the farming household."
)


class ReportRenderError(RuntimeError):
    pass


class PublicReportPrivacyError(ReportRenderError):
    """El HTML de un informe 'public' contiene datos sensibles; se aborta la generación."""


@dataclass
class FetchGuard:
    """Política de recursos externos: solo ``data:``. Registra los intentos denegados.

    Se enlaza a WeasyPrint mediante ``build_url_fetcher`` (subclase de ``URLFetcher`` de WeasyPrint 70).
    """

    denied: list[str] = field(default_factory=list)
    allowed_data_uris: int = 0

    def check(self, url: str) -> None:
        scheme = url.split(":", 1)[0].lower() if ":" in url else ""
        if scheme == "data":
            self.allowed_data_uris += 1
            return
        self.denied.append(re.sub(r"[?#].*$", "", url)[:200])  # sin query: puede llevar secretos
        raise ValueError("Recurso externo denegado por política de seguridad del informe")

    __call__ = check


def build_url_fetcher(guard: FetchGuard) -> Any:
    """``URLFetcher`` de WeasyPrint 70 con doble barrera: nuestra política + ``allowed_protocols``."""
    from weasyprint.urls import URLFetcher

    class GuardedFetcher(URLFetcher):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(
                timeout=1, allowed_protocols=["data"], allow_redirects=False, fail_on_errors=False
            )

        def fetch(self, url: str, headers: Any = None) -> Any:
            guard.check(url)  # registra y deniega todo lo que no sea data:
            return super().fetch(url, headers)

    return GuardedFetcher()


def _env() -> SandboxedEnvironment:
    return SandboxedEnvironment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"], default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(data: ReportInput) -> str:
    env = _env()
    # CSS propio del repositorio (no proviene de la entrada): se marca seguro para no escapar comillas.
    css = Markup((TEMPLATES_DIR / CSS_NAME).read_text(encoding="utf-8"))  # noqa: S704
    created = data.generated_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    html = env.get_template(TEMPLATE_NAME).render(
        r=data,
        css=css,
        created=created,
        template_version=TEMPLATE_VERSION,
        disclaimer_es=DISCLAIMER_ES,
        disclaimer_en=DISCLAIMER_EN,
        show_internal=data.privacy_level == "internal",
        bilingual=data.locale == "es+en",
    )
    if data.privacy_level == "public":
        problems = find_sensitive(html)
        if problems:
            raise PublicReportPrivacyError(
                f"El informe público contiene datos sensibles ({', '.join(problems)})"
            )
    return html


_LOCAL_CSS_LINK = re.compile(
    r'<link\s+rel="stylesheet"\s+href="([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.css)"\s*/?>'
)
_CSS_FORBIDDEN = re.compile(r"url\s*\(|@import|</", re.IGNORECASE)


def inline_local_stylesheets(html: str, templates_dir: Path = TEMPLATES_DIR) -> str:
    """Sustituye ``<link rel="stylesheet" href="x.css">`` por ``<style>`` con el CSS de la carpeta.

    La política de red del renderizador sigue siendo «solo ``data:``»: en vez de permitir lectura
    de archivos, los estilos locales del paquete de plantillas se incrustan antes de renderizar.
    Solo se aceptan nombres simples (sin rutas), archivos regulares dentro de ``templates_dir`` y
    CSS sin ``url()``/``@import`` (que reintroducirían recursos externos). El enlace proviene de la
    plantilla; el texto de usuario llega escapado por autoescape y no puede formar un ``<link>``.
    """
    root = templates_dir.resolve()

    def replace(match: re.Match[str]) -> str:
        path = (root / match.group(1)).resolve()
        if path.parent != root or not path.is_file():
            raise ReportRenderError(
                "Hoja de estilo local no encontrada en la carpeta de plantillas"
            )
        css = path.read_text(encoding="utf-8")
        if _CSS_FORBIDDEN.search(css):
            raise ReportRenderError("La hoja de estilo no puede usar url(), @import ni '</'")
        return f"<style>{css}</style>"

    return _LOCAL_CSS_LINK.sub(replace, html)


def render_template_pack(
    template_name: str,
    context: dict[str, Any],
    *,
    privacy_level: str,
    templates_dir: Path = TEMPLATES_DIR,
) -> str:
    """Renderiza una plantilla Jinja2 de un paquete (p. ej. la de R4) en el entorno restringido.

    No define el *contexto*: lo arma quien llama a partir de ``report_model`` (R2). Aplica el mismo
    sandbox/autoescape/``StrictUndefined``, incrusta estilos locales y, si el informe es ``public``,
    aborta cuando el HTML contiene datos sensibles.
    """
    env = SandboxedEnvironment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml", "j2"], default_for_string=True),
        undefined=StrictUndefined,
    )
    html = inline_local_stylesheets(
        env.get_template(template_name).render(**context), templates_dir
    )
    if privacy_level == "public":
        problems = find_sensitive(html)
        if problems:
            raise PublicReportPrivacyError(
                f"El informe público contiene datos sensibles ({', '.join(problems)})"
            )
    return html


def html_to_pdf(html: str, guard: FetchGuard | None = None) -> bytes:
    """Convierte HTML a PDF. Importa WeasyPrint de forma perezosa (requiere Pango nativo)."""
    try:
        from weasyprint import HTML
    except OSError as exc:  # bibliotecas nativas ausentes (p. ej. host Windows)
        raise ReportRenderError(
            "WeasyPrint no pudo cargar sus bibliotecas nativas (Pango). "
            "Ejecute dentro de la imagen Docker (infra/Dockerfile.app)."
        ) from exc
    guard = guard or FetchGuard()
    document = HTML(string=html, base_url=None, url_fetcher=build_url_fetcher(guard))
    return bytes(document.write_pdf())
