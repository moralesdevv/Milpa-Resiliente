"""PDF A4 del informe de decisión con ReportLab: Python puro, sin Pango, sin GTK, sin Docker.

Entrada: el mismo ``ReportInput`` que muestra la vista web (el modelo de informe del motor ya adaptado). Esta
capa SOLO presenta: no calcula ninguna cifra. El PDF es determinista (``invariant``): la misma entrada produce
exactamente los mismos bytes.

Privacidad: con ``privacy_level='public'`` no se imprime ningún campo interno y se escanea TODO el texto en
busca de coordenadas precisas, correos o tokens antes de dibujar nada.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from api.reports.contract import ReportInput, ReportSection, ReportTable
from api.reports.renderer import (
    DISCLAIMER_EN,
    DISCLAIMER_ES,
    PublicReportPrivacyError,
    ReportRenderError,
)
from api.security.privacy import find_sensitive, iter_strings

PDF_ENGINE = "reportlab"
GREEN = colors.HexColor("#073b2a")
MAIZE = colors.HexColor("#ffc933")
SAND = colors.HexColor("#f5efdc")
LINE = colors.HexColor("#c9bfa5")
INK = colors.HexColor("#14261e")
_URL = re.compile(r"(https?://[^\s<>\"']+)")

# Caracteres que la fuente incluida con ReportLab no trae: se reemplazan por un equivalente legible.
_REPLACEMENTS = {
    "\u2192": "->",
    "\u2190": "<-",
    "\u2212": "-",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2248": "~",
    "\u2026": "...",
    "\u2011": "-",
    "\u00a0": " ",
}
_FONTS_READY = False


def _register_fonts() -> None:
    global _FONTS_READY  # noqa: PLW0603 - registro idempotente de fuentes
    if _FONTS_READY:
        return
    folder = Path(reportlab.__file__).resolve().parent / "fonts"
    files = {
        "Vera": "Vera.ttf",
        "Vera-Bold": "VeraBd.ttf",
        "Vera-Italic": "VeraIt.ttf",
        "Vera-BoldItalic": "VeraBI.ttf",
    }
    for name, filename in files.items():
        pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    registerFontFamily(
        "Vera", normal="Vera", bold="Vera-Bold", italic="Vera-Italic", boldItalic="Vera-BoldItalic"
    )
    _FONTS_READY = True


def _supported(char: str) -> bool:
    face = pdfmetrics.getFont("Vera").face
    return ord(char) in face.charToGlyph


def _clean(text: str) -> str:
    """Texto seguro para la fuente: reemplaza símbolos no disponibles y descarta los que no existen."""
    out: list[str] = []
    for original in text:
        for piece in _REPLACEMENTS.get(original, original):
            if piece in "\n\t" or _supported(piece):
                out.append(piece)
            else:
                out.append("?")
    return "".join(out)


def _inline(text: str) -> str:
    """Escapa para Paragraph y vuelve clicables las URL (https://…)."""
    safe = escape(_clean(text))
    return _URL.sub(
        lambda m: f'<link href="{m.group(1)}" color="#0b659f">{m.group(1)}</link>', safe
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "base", fontName="Vera", fontSize=9, leading=12.5, textColor=INK, alignment=TA_LEFT
    )
    return {
        "base": base,
        "small": ParagraphStyle(
            "small", parent=base, fontSize=7.5, leading=10, textColor=colors.HexColor("#4d6056")
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base,
            fontName="Vera-Bold",
            fontSize=17,
            leading=21,
            textColor=GREEN,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Vera-Bold",
            fontSize=11.5,
            leading=15,
            textColor=GREEN,
            spaceBefore=10,
            spaceAfter=3,
            keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base,
            fontName="Vera-Bold",
            fontSize=9.5,
            leading=13,
            spaceBefore=4,
            keepWithNext=1,
        ),
        "en": ParagraphStyle(
            "en", parent=base, fontName="Vera-Italic", textColor=colors.HexColor("#2d4a3d")
        ),
        "banner": ParagraphStyle(
            "banner",
            parent=base,
            fontName="Vera-Bold",
            fontSize=8.5,
            leading=11.5,
            backColor=colors.HexColor("#fff0bd"),
            borderColor=MAIZE,
            borderWidth=0.8,
            borderPadding=5,
            textColor=colors.HexColor("#5c3d00"),
            spaceAfter=8,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.6, leading=9.8),
        "cellh": ParagraphStyle(
            "cellh",
            parent=base,
            fontName="Vera-Bold",
            fontSize=7.6,
            leading=9.8,
            textColor=colors.white,
        ),
        "mono": ParagraphStyle("mono", parent=base, fontName="Courier", fontSize=7, leading=9),
        "disc": ParagraphStyle(
            "disc",
            parent=base,
            fontName="Vera-Italic",
            fontSize=8,
            leading=11,
            borderColor=LINE,
            borderWidth=0.6,
            borderPadding=5,
            spaceBefore=8,
        ),
    }


class _NumberedCanvas(Canvas):
    """Canvas que conoce el total de páginas para el pie «Página X de Y»."""

    footer_text = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total: int) -> None:
        self.setStrokeColor(LINE)
        self.setLineWidth(0.5)
        self.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        self.setFont("Vera", 7)
        self.setFillColor(colors.HexColor("#4d6056"))
        self.drawString(18 * mm, 10 * mm, _clean(self.footer_text))
        label = f"Página {self._pageNumber} de {total} / Page {self._pageNumber} of {total}"
        self.drawRightString(A4[0] - 18 * mm, 10 * mm, label)


def _paragraphs(text: str, style: ParagraphStyle) -> list[Paragraph]:
    return [Paragraph(_inline(chunk), style) for chunk in text.split("\n") if chunk.strip()]


def _bullets(
    items: Iterable[str], styles: dict[str, ParagraphStyle], *, english: bool = False
) -> ListFlowable:
    style = styles["en"] if english else styles["base"]
    return ListFlowable(
        [ListItem(Paragraph(_inline(item), style), leftIndent=10) for item in items],
        bulletType="bullet",
        bulletFontName="Vera",
        bulletFontSize=7,
        start="•",
        leftIndent=10,
    )


def _table(
    table: ReportTable, width: float, styles: dict[str, ParagraphStyle], bilingual: bool
) -> list[Any]:
    flow: list[Any] = []
    caption = table.caption_es or ""
    if bilingual and table.caption_en:
        caption = f"{caption} / {table.caption_en}" if caption else table.caption_en
    if caption:
        flow.append(Paragraph(_inline(caption), styles["small"]))
    cols = len(table.headers)
    if table.weights:
        total = sum(table.weights)
        widths = [width * w / total for w in table.weights]
    else:
        # La primera columna (nombre) recibe más ancho; el resto se reparte por igual.
        first = min(width * 0.32, width / cols * 1.7) if cols > 2 else width / cols
        rest = (width - first) / max(cols - 1, 1)
        widths = [first] + [rest] * (cols - 1)
    data = [[Paragraph(_inline(h), styles["cellh"]) for h in table.headers]]
    data += [[Paragraph(_inline(cell), styles["cell"]) for cell in row] for row in table.rows]
    grid = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("LINEBELOW", (0, 0), (-1, 0), 1, MAIZE),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    for index in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, index), (-1, index), SAND))
    grid.setStyle(TableStyle(style))
    flow.append(grid)
    flow.append(Spacer(1, 5))
    return flow


def _section(
    section: ReportSection, width: float, styles: dict[str, ParagraphStyle], bilingual: bool
) -> list[Any]:
    title = section.title_es
    if bilingual and section.title_en:
        title = f"{title} / {section.title_en}"
    flow: list[Any] = [Paragraph(_inline(title), styles["h2"])]
    flow += _paragraphs(section.body_es, styles["base"])
    if bilingual and section.body_en:
        flow += _paragraphs(section.body_en, styles["en"])
    if section.items:
        flow.append(Spacer(1, 2))
        flow.append(_bullets(section.items, styles))
    if bilingual and section.items_en:
        flow.append(Spacer(1, 2))
        flow.append(_bullets(section.items_en, styles, english=True))
    if section.table:
        flow.append(Spacer(1, 3))
        flow += _table(section.table, width, styles, bilingual)
    return flow


def _all_text(data: ReportInput) -> str:
    return "\n".join(iter_strings(data.model_dump(mode="json")))


def render_pdf(data: ReportInput) -> bytes:
    """Devuelve el PDF A4 del informe. Lanza ``PublicReportPrivacyError`` si un informe público filtra datos."""
    if data.privacy_level == "public":
        problems = find_sensitive(_all_text(data))
        if problems:
            raise PublicReportPrivacyError(
                f"El informe público contiene datos sensibles ({', '.join(problems)})"
            )
    try:
        _register_fonts()
        return _build(data)
    except ReportRenderError:
        raise
    except Exception as exc:
        raise ReportRenderError(f"No se pudo generar el PDF ({type(exc).__name__})") from exc


def _build(data: ReportInput) -> bytes:
    styles = _styles()
    bilingual = data.locale == "es+en"
    buffer = io.BytesIO()
    created = data.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    footer = f"MILPA RESILIENTE 3.3 · {data.zone_name} · run {str(data.run_id)[:8] if data.run_id else '-'} · {data.privacy_level}"

    class Canvas_(_NumberedCanvas):
        footer_text = footer

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=19 * mm,
        title=_clean(
            f"MILPA RESILIENTE — Informe de decisión / Decision report — {data.zone_name}"
        ),
        author="MILPA RESILIENTE",
        subject="Climate-exposure comparison of agricultural strategies (sandbox, provisional)",
        creator=f"milpa-api {PDF_ENGINE}",
        invariant=1,
    )
    width = A4[0] - 36 * mm
    story: list[Any] = []
    if data.provisional_banner:
        story.append(
            Paragraph(
                _inline(
                    "RESULTADO PROVISIONAL (modo sandbox): umbrales y catálogos sin cita; no usar para decidir sin validación local. / PROVISIONAL RESULT (sandbox mode): thresholds and catalogs are uncited; do not decide without local validation."
                ),
                styles["banner"],
            )
        )
    story.append(Paragraph(_inline(f"Informe de decisión — {data.zone_name}"), styles["h1"]))
    if bilingual:
        story.append(Paragraph(_inline(f"Decision report — {data.zone_name}"), styles["en"]))
    story.append(
        Paragraph(
            _inline(f"Generado {created} · nivel de privacidad: {data.privacy_level}"),
            styles["small"],
        )
    )
    if data.privacy_level == "internal" and data.internal:
        extra = " · ".join(
            x for x in (data.internal.farmer_display_name, data.internal.parcel_code) if x
        )
        if extra:
            story.append(Paragraph(_inline(f"Uso interno: {extra}"), styles["small"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=MAIZE, spaceBefore=4, spaceAfter=6))

    story.append(Paragraph("Resumen" + (" / Summary" if bilingual else ""), styles["h2"]))
    story += _paragraphs(data.summary_es, styles["base"])
    if bilingual and data.summary_en:
        story += _paragraphs(data.summary_en, styles["en"])
    for section in data.sections:
        story += _section(section, width, styles, bilingual)
    story.append(
        Paragraph(
            _inline(DISCLAIMER_ES + (f"\n{DISCLAIMER_EN}" if bilingual else "")).replace(
                "\n", "<br/>"
            ),
            styles["disc"],
        )
    )

    story.append(PageBreak())
    story.append(
        Paragraph("Anexo técnico" + (" / Technical annex" if bilingual else ""), styles["h1"])
    )
    ids = [
        ["run_id", str(data.run_id) if data.run_id else "— (sin corrida asociada)"],
        ["code_version", data.hashes.code_version],
        ["region_config_hash", data.hashes.region_config_hash],
        ["catalog_hash", data.hashes.catalog_hash],
        ["data_hash", data.hashes.data_hash],
        ["params_hash", data.hashes.params_hash],
        ["seed", str(data.hashes.seed)],
    ]
    id_table = Table(
        [
            [Paragraph(_inline(k), styles["cellh"]), Paragraph(_inline(v), styles["mono"])]
            for k, v in ids
        ],
        colWidths=[40 * mm, width - 40 * mm],
    )
    id_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GREEN),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(
        KeepTogether(
            [
                Paragraph(
                    "Identificadores de reproducibilidad"
                    + (" / Reproducibility identifiers" if bilingual else ""),
                    styles["h2"],
                ),
                id_table,
            ]
        )
    )
    for section in data.annex:
        story += _section(section, width, styles, bilingual)
    for title, items in (
        ("Procedencia y evidencia / Provenance and evidence", data.provenance_notes),
        ("Supuestos / Assumptions", data.assumptions),
        ("Limitaciones / Limitations", data.limitations),
    ):
        story.append(
            Paragraph(_inline(title if bilingual else title.split(" / ")[0]), styles["h2"])
        )
        story.append(_bullets(items, styles) if items else Paragraph("—", styles["base"]))
    story.append(Paragraph("Referencias" + (" / References" if bilingual else ""), styles["h2"]))
    if data.references:
        story.append(
            ListFlowable(
                [
                    ListItem(
                        Paragraph(
                            _inline(
                                ref.text
                                + (
                                    f" (versión / version: {ref.product_version})"
                                    if ref.product_version
                                    else ""
                                )
                            ),
                            styles["base"],
                        ),
                        leftIndent=14,
                    )
                    for ref in data.references
                ],
                bulletType="1",
                bulletFontName="Vera",
                bulletFontSize=8,
                leftIndent=14,
            )
        )
    else:
        story.append(Paragraph("Sin referencias en la entrada.", styles["base"]))
    doc.build(story, canvasmaker=Canvas_)
    return buffer.getvalue()
