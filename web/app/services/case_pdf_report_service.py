from dataclasses import dataclass
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .preview_service import ensure_preview_for_path
from .simulation_results_service import build_mpc_results_view, get_result_image_path
from .storage_service import resolve_stored_directory, resolve_stored_path


@dataclass(frozen=True)
class CasePdfReport:
    filename: str
    buffer: BytesIO


def build_case_pdf_report(case, upload_folder):
    paths = _build_case_paths(case, upload_folder)
    results_view = build_mpc_results_view(paths["results_dir"])
    styles = _build_styles()
    story = []

    story.extend(_build_cover(case, styles))
    story.extend(_build_case_summary(case, styles))
    story.extend(_build_main_image_section(paths, styles))
    story.extend(_build_result_flow_section(results_view, styles))
    story.extend(_build_results_reading_section(results_view, styles))
    story.extend(_build_metric_section(results_view, styles))
    story.extend(_build_map_sections(paths["results_dir"], results_view, styles))
    story.extend(_build_glossary_section(results_view, styles))
    story.extend(_build_final_notice(styles))

    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Reporte visual del caso {case.id}",
        author="Prototipo Mamografico",
    )
    document.build(story)
    pdf_buffer.seek(0)

    return CasePdfReport(
        filename=f"caso_{case.id}_reporte_visual.pdf",
        buffer=pdf_buffer,
    )


def _build_styles():
    base_styles = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#084766"),
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#435469"),
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "ReportSection",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#084766"),
            spaceBefore=14,
            spaceAfter=8,
        ),
        "subsection": ParagraphStyle(
            "ReportSubsection",
            parent=base_styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#172033"),
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#172033"),
        ),
        "muted": ParagraphStyle(
            "ReportMuted",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#5f6f85"),
        ),
        "notice": ParagraphStyle(
            "ReportNotice",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#6f4a18"),
            backColor=colors.HexColor("#fff8eb"),
            borderColor=colors.HexColor("#f2d39b"),
            borderWidth=0.7,
            borderPadding=7,
            spaceAfter=12,
        ),
        "center": ParagraphStyle(
            "ReportCenter",
            parent=base_styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#5f6f85"),
        ),
    }

    return styles


def _build_cover(case, styles):
    return [
        Paragraph(f"Reporte visual del caso #{case.id}", styles["title"]),
        Paragraph(
            "Resumen explicativo de la ROI, los mapas y las metricas generadas "
            "por el prototipo de simulacion mesoscopica.",
            styles["subtitle"],
        ),
        Paragraph(
            "Uso academico: este reporte no constituye diagnostico clinico, no "
            "clasifica lesiones y no reemplaza la evaluacion medica profesional.",
            styles["notice"],
        ),
    ]


def _build_case_summary(case, styles):
    rows = (
        ("ID del caso", case.id),
        ("Fecha de carga", _format_datetime(case.created_at)),
        ("Estado", _format_status(case.status)),
        ("Modalidad", _format_input_mode(case.input_mode)),
        ("Archivo cargado", case.original_filename or "No registrado"),
        ("Tamano", _format_file_size(case.file_size_bytes)),
    )

    return [
        Paragraph("Datos principales", styles["section"]),
        _build_key_value_table(rows, styles),
    ]


def _build_main_image_section(paths, styles):
    image_path = paths["roi"] if paths["roi"] is not None else paths["original"]
    title = "ROI usada en el analisis" if paths["roi"] is not None else "Imagen cargada"
    explanation = (
        "Esta es la region de interes usada como entrada visual del analisis."
        if paths["roi"] is not None
        else "Cuando no existe ROI asociada, se muestra la imagen cargada como referencia."
    )
    image_flowable = _build_image_flowable(image_path, max_width=15.5 * cm, max_height=8 * cm)

    section = [
        Paragraph(title, styles["section"]),
        Paragraph(explanation, styles["body"]),
        Spacer(1, 8),
    ]

    if image_flowable is not None:
        section.extend([image_flowable, Spacer(1, 8)])
    else:
        section.append(Paragraph("No hay vista previa disponible para esta imagen.", styles["muted"]))

    return section


def _build_result_flow_section(results_view, styles):
    if not results_view["available"]:
        return []

    reading_steps = results_view.get("reading_steps") or ()
    if not reading_steps:
        return []

    rows = [(item["label"], item["detail"]) for item in reading_steps]

    return [
        Paragraph("De la ROI al resultado", styles["section"]),
        Paragraph(
            "Esta guia muestra como una imagen recortada termina convertida en "
            "mapas y metricas. La idea central es que la mamografia no se interpreta "
            "directamente como diagnostico: primero se transforma en un dominio "
            "matematico para simular movimiento de particulas.",
            styles["body"],
        ),
        Spacer(1, 8),
        _build_key_value_table(rows, styles),
    ]


def _build_results_reading_section(results_view, styles):
    if not results_view["interpretation_items"]:
        return [
            Paragraph("Lectura de resultados", styles["section"]),
            Paragraph(
                "Aun no existen resultados MPC suficientes para generar una lectura "
                "explicativa del caso.",
                styles["body"],
            ),
        ]

    rows = [
        (item["label"], item["detail"])
        for item in results_view["interpretation_items"]
    ]

    return [
        Paragraph("Lectura de resultados", styles["section"]),
        Paragraph(
            "Las siguientes frases traducen las metricas principales a una lectura "
            "mas simple para usuario final y para documentacion academica.",
            styles["body"],
        ),
        Spacer(1, 8),
        _build_key_value_table(rows, styles),
    ]


def _build_metric_section(results_view, styles):
    if not results_view["primary_metrics"]:
        return []

    rows = [
        (metric["label"], metric["value"], metric["hint"])
        for metric in results_view["primary_metrics"]
    ]

    return [
        Paragraph("Metricas principales", styles["section"]),
        _build_metric_table(rows, styles),
    ]


def _build_map_sections(results_dir, results_view, styles):
    if results_dir is None:
        return []

    primary_maps = list(results_view["concentration_maps"])
    if results_view.get("autocorrelation_chart"):
        primary_maps.append(results_view["autocorrelation_chart"])
    model_maps = list(results_view["domain_maps"])
    if not primary_maps and not model_maps:
        return []

    story = [PageBreak()]
    if primary_maps:
        story.append(Paragraph("Imagenes principales de resultados", styles["section"]))
        _append_result_maps(story, results_dir, primary_maps, styles)
    if model_maps:
        story.append(Paragraph("Construccion del modelo de simulacion", styles["section"]))
        story.append(
            Paragraph(
                "Estas vistas explican como la ROI se delimito y se transformo en "
                "la caja y los obstaculos usados por el simulador.",
                styles["muted"],
            )
        )
        _append_result_maps(story, results_dir, model_maps, styles)

    return story


def _append_result_maps(story, results_dir, maps, styles):

    for result_map in maps:
        path = get_result_image_path(results_dir, result_map["key"])
        if path is None or not path.exists():
            continue

        image_flowable = _build_image_flowable(path, max_width=14.5 * cm, max_height=7.2 * cm)
        block = [
            Paragraph(result_map["title"], styles["subsection"]),
            Paragraph(result_map["description"], styles["body"]),
            Paragraph(result_map["reading"], styles["muted"]),
        ]
        if result_map.get("stat"):
            stat = result_map["stat"]
            block.append(
                Paragraph(
                    f"{_safe_text(stat['label'])}: <b>{_safe_text(stat['value'])}</b> "
                    f"({_safe_text(stat['detail'])})",
                    styles["body"],
                )
            )
        if result_map.get("sampling_note"):
            block.append(Paragraph(result_map["sampling_note"], styles["muted"]))
        if result_map.get("legend"):
            legend_text = "<br/>".join(
                f"- {_safe_text(item)}" for item in result_map["legend"]
            )
            block.append(Paragraph(legend_text, styles["muted"]))
        block.append(Spacer(1, 6))

        if image_flowable is not None:
            block.append(image_flowable)

        block.append(Spacer(1, 10))
        story.append(KeepTogether(block))


def _build_glossary_section(results_view, styles):
    if not results_view["concept_items"]:
        return []

    rows = [(item["term"], item["meaning"]) for item in results_view["concept_items"]]

    return [
        Paragraph("Glosario breve", styles["section"]),
        _build_key_value_table(rows, styles),
    ]


def _build_final_notice(styles):
    return [
        Paragraph("Alcance del reporte", styles["section"]),
        Paragraph(
            "Los mapas y metricas describen el comportamiento de una simulacion "
            "computacional sobre la ROI. No son una nueva mamografia, no identifican "
            "diagnosticos y deben interpretarse solo dentro del alcance academico "
            "del prototipo.",
            styles["notice"],
        ),
    ]


def _build_key_value_table(rows, styles):
    table_data = [
        [Paragraph(_safe_text(label), styles["subsection"]), Paragraph(_safe_text(value), styles["body"])]
        for label, value in rows
    ]
    table = Table(table_data, colWidths=[5.1 * cm, 10.4 * cm], hAlign="LEFT")
    table.setStyle(_table_style())
    return table


def _build_metric_table(rows, styles):
    table_data = [
        [
            Paragraph("Metrica", styles["subsection"]),
            Paragraph("Valor", styles["subsection"]),
            Paragraph("Que significa", styles["subsection"]),
        ]
    ]

    for label, value, hint in rows:
        table_data.append(
            [
                Paragraph(_safe_text(label), styles["body"]),
                Paragraph(_safe_text(value), styles["body"]),
                Paragraph(_safe_text(hint), styles["body"]),
            ]
        )

    table = Table(table_data, colWidths=[5.1 * cm, 2.5 * cm, 7.9 * cm], hAlign="LEFT")
    table.setStyle(_table_style(header=True))
    return table


def _table_style(header=False):
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#ccd6e2")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ccd6e2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]

    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#084766")),
            ]
        )

    return TableStyle(commands)


def _build_image_flowable(path, *, max_width, max_height):
    preview_path = _get_preview_path(path)
    if preview_path is None:
        return None

    try:
        with PILImage.open(preview_path) as image:
            width, height = image.size
    except (OSError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    scale = min(max_width / width, max_height / height, 1)
    return RLImage(str(preview_path), width=width * scale, height=height * scale)


def _get_preview_path(path):
    if path is None or not path.exists():
        return None

    try:
        preview = ensure_preview_for_path(path)
    except (OSError, TypeError, ValueError):
        return None

    if preview is None:
        return None

    return preview.absolute_path


def _build_case_paths(case, upload_folder):
    upload_folder_path = Path(upload_folder)
    case_dir = upload_folder_path / f"case_{case.id}"

    return {
        "original": resolve_stored_path(case.original_file_path, str(upload_folder_path)),
        "roi": resolve_stored_path(case.roi_file_path, str(upload_folder_path)),
        "results_dir": _resolve_results_dir(case, upload_folder_path, case_dir),
    }


def _resolve_results_dir(case, upload_folder_path, case_dir):
    configured_dir = resolve_stored_directory(
        case.simulation_results_path,
        str(upload_folder_path),
    )

    if configured_dir is not None and configured_dir.exists():
        return configured_dir

    fallback_dir = case_dir / "results"
    if fallback_dir.exists():
        return fallback_dir

    return None


def _safe_text(value):
    return escape(str(value if value is not None else "No registrado"))


def _format_datetime(value):
    if value is None:
        return "No registrada"

    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_file_size(size_bytes):
    if size_bytes is None:
        return "No registrado"

    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"

    return f"{size_bytes} bytes"


def _format_input_mode(input_mode):
    if input_mode == "roi_recortada":
        return "ROI recortada"

    return "Mamografia completa"


def _format_status(status):
    labels = {
        "registrado": "Registrado",
        "roi_confirmada": "ROI confirmada",
        "pendiente": "En cola",
        "procesando": "Procesando",
        "completado": "Completado",
        "error": "Error",
        "notificado": "Notificado",
    }

    return labels.get(status, status or "No registrado")
