from flask import Blueprint, render_template, url_for

from ..models import Case, CaseStatus, InputMode
from ..services.auth_service import get_current_user


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    user = get_current_user()
    dashboard_summary = None
    recent_cases = []
    continuation_case = None
    latest_result = None

    if user is not None:
        user_cases = (
            Case.query.filter_by(user_id=user.id)
            .order_by(Case.created_at.desc())
            .all()
        )
        dashboard_summary = _build_dashboard_summary(user_cases)
        recent_cases = [_build_recent_case(case) for case in user_cases[:3]]

        pending_case = next(
            (case for case in user_cases if not _is_completed(case)),
            None,
        )
        completed_case = next(
            (case for case in user_cases if _is_completed(case)),
            None,
        )

        if pending_case is not None:
            continuation_case = _build_continuation_case(pending_case)

        if completed_case is not None:
            latest_result = _build_latest_result(completed_case)

    return render_template(
        "index.html",
        dashboard_summary=dashboard_summary,
        recent_cases=recent_cases,
        continuation_case=continuation_case,
        latest_result=latest_result,
    )


def _build_dashboard_summary(cases):
    return {
        "total": len(cases),
        "completed": sum(1 for case in cases if _is_completed(case)),
        "processing": sum(
            1
            for case in cases
            if case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING}
        ),
    }


def _build_recent_case(case):
    return {
        "id": case.id,
        "created_at": _format_datetime(case.created_at),
        "input_mode": _format_input_mode(case.input_mode),
        "status": case.status,
        "status_label": _format_status(case.status),
        "filename": (
            case.original_filename or case.roi_filename or "Archivo registrado"
        ),
        "detail_url": url_for("upload.case_detail", case_id=case.id),
    }


def _build_continuation_case(case):
    title, message = _get_continuation_copy(case)

    return {
        "id": case.id,
        "title": title,
        "message": message,
        "status": case.status,
        "status_label": _format_status(case.status),
        "detail_url": url_for("upload.case_detail", case_id=case.id),
    }


def _build_latest_result(case):
    stored_result = case.result
    has_density_map = bool(case.simulation_density_map_file_path)

    return {
        "id": case.id,
        "created_at": _format_datetime(case.created_at),
        "input_mode": _format_input_mode(case.input_mode),
        "detail_url": url_for("upload.case_detail", case_id=case.id)
        + "#simulation-results",
        "image_url": (
            url_for(
                "upload.case_simulation_result_image",
                case_id=case.id,
                result_key="density_map",
            )
            if has_density_map
            else None
        ),
        "mdc": _format_decimal(stored_result.mdc if stored_result else None),
        "mdc_star": _format_percent(
            stored_result.mdc_star if stored_result else None,
        ),
    }


def _get_continuation_copy(case):
    if case.status == CaseStatus.ERROR:
        return (
            "Revisar procesamiento",
            "El caso necesita atención antes de poder continuar.",
        )

    if case.status == CaseStatus.PROCESSING:
        return (
            "Simulación en curso",
            "El caso se está procesando y se actualizará al finalizar.",
        )

    if case.status == CaseStatus.PENDING:
        return (
            "Simulación en espera",
            "El caso está en cola y comenzará a procesarse automáticamente.",
        )

    if case.input_mode == InputMode.MAMMOGRAM and not case.roi_file_path:
        return (
            "Seleccionar la ROI",
            "La mamografía está lista para definir la región que se analizará.",
        )

    if case.roi_file_path and case.status == CaseStatus.REGISTERED:
        return (
            "Confirmar la ROI",
            "La región está preparada para que la revises y confirmes.",
        )

    if case.status == CaseStatus.ROI_CONFIRMED:
        return (
            "Preparar simulación",
            "La ROI fue confirmada y está lista para continuar el procesamiento.",
        )

    return (
        "Continuar análisis",
        "Abre el caso para revisar su estado y completar el siguiente paso.",
    )


def _format_datetime(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "Sin fecha"


def _format_decimal(value):
    if value is None:
        return "No disponible"

    return f"{value:.4f}"


def _format_percent(value):
    if value is None:
        return "No disponible"

    return f"{value * 100:.2f}%"


def _is_completed(case):
    return case.status in {CaseStatus.COMPLETED, CaseStatus.NOTIFIED}


def _format_input_mode(input_mode):
    labels = {
        InputMode.MAMMOGRAM: "Mamografia completa",
        InputMode.ROI: "ROI recortada",
    }
    return labels.get(input_mode, "Entrada registrada")


def _format_status(status):
    labels = {
        CaseStatus.REGISTERED: "Registrado",
        CaseStatus.ROI_CONFIRMED: "ROI confirmada",
        CaseStatus.PENDING: "En cola",
        CaseStatus.PROCESSING: "Procesando",
        CaseStatus.COMPLETED: "Completado",
        CaseStatus.ERROR: "Error",
        CaseStatus.NOTIFIED: "Notificado",
    }
    return labels.get(status, status or "Sin estado")
