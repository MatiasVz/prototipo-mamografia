from flask import Blueprint, render_template, url_for

from ..models import Case, CaseStatus, InputMode
from ..services.auth_service import get_current_user


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    user = get_current_user()
    dashboard_summary = None
    recent_cases = []

    if user is not None:
        user_cases = (
            Case.query.filter_by(user_id=user.id)
            .order_by(Case.created_at.desc())
            .all()
        )
        dashboard_summary = _build_dashboard_summary(user_cases)
        recent_cases = [_build_recent_case(case) for case in user_cases[:4]]

    return render_template(
        "index.html",
        dashboard_summary=dashboard_summary,
        recent_cases=recent_cases,
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
        "attention": sum(1 for case in cases if _case_needs_attention(case)),
    }


def _build_recent_case(case):
    action = _get_case_action(case)

    return {
        "id": case.id,
        "created_at": _format_datetime(case.created_at),
        "input_mode": _format_input_mode(case.input_mode),
        "status": case.status,
        "status_label": _format_status(case.status),
        "filename": case.original_filename or case.roi_filename or "Archivo registrado",
        "action_label": action["label"],
        "action_url": action["url"],
    }


def _case_needs_attention(case):
    if case.status == CaseStatus.ERROR:
        return True

    if _is_completed(case) or case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING}:
        return False

    return True


def _get_case_action(case):
    detail_url = url_for("upload.case_detail", case_id=case.id)

    if _is_completed(case):
        return {"label": "Ver resultados", "url": f"{detail_url}#simulation-results"}

    if case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING}:
        return {"label": "Seguir estado", "url": detail_url}

    if case.status == CaseStatus.ERROR:
        return {"label": "Revisar error", "url": detail_url}

    if case.input_mode == InputMode.MAMMOGRAM and not case.roi_file_path:
        return {
            "label": "Recortar ROI",
            "url": url_for("upload.crop_case_roi", case_id=case.id),
        }

    if case.roi_file_path and case.status == CaseStatus.REGISTERED:
        return {"label": "Confirmar ROI", "url": detail_url}

    if case.status == CaseStatus.ROI_CONFIRMED:
        return {"label": "Preparar simulacion", "url": detail_url}

    return {"label": "Ver detalle", "url": detail_url}


def _format_datetime(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "Sin fecha"


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
