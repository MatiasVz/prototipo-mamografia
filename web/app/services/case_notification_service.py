from flask import current_app

from .email_service import EmailDeliveryError, send_email


CASE_COMPLETED_SUBJECT = "Caso procesado en el Prototipo Mamografico"


def notify_case_completed(case):
    """Enviar un aviso al usuario cuando el caso termina de procesarse.

    La notificacion es auxiliar: si falla, se registra el problema en logs, pero
    no se cambia el estado del caso ni se invalida el resultado de la simulacion.
    """
    user = getattr(case, "user", None)

    if user is None or not user.email:
        current_app.logger.info(
            "No se envio notificacion del caso %s: no hay usuario asociado.",
            case.id,
        )
        return False

    body = _build_case_completed_email_body(case, user)

    try:
        send_email(user.email, CASE_COMPLETED_SUBJECT, body)
    except EmailDeliveryError:
        current_app.logger.exception(
            "No se pudo enviar la notificacion de caso completado. "
            "case_id=%s user_id=%s",
            case.id,
            user.id,
        )
        return False

    current_app.logger.info(
        "Notificacion de caso completado enviada. case_id=%s user_id=%s",
        case.id,
        user.id,
    )
    return True


def _build_case_completed_email_body(case, user):
    greeting = f"Hola {user.name}," if user.name else "Hola,"
    case_url = _build_case_detail_url(case)
    review_instruction = (
        f"Puedes revisar los resultados ingresando a este enlace:\n{case_url}"
        if case_url
        else (
            "Puedes revisar los resultados iniciando sesion en el prototipo "
            "y entrando a la seccion Mis casos."
        )
    )

    return (
        f"{greeting}\n\n"
        f"El procesamiento del caso #{case.id} finalizo correctamente.\n\n"
        f"{review_instruction}\n\n"
        "Recuerda que este sistema es un prototipo academico/de investigacion "
        "y no debe interpretarse como una herramienta de diagnostico clinico.\n\n"
        "Si no reconoces esta actividad, puedes ignorar este correo.\n"
    )


def _build_case_detail_url(case):
    base_url = current_app.config.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

    if not base_url:
        return ""

    return f"{base_url}/mamografias/casos/{case.id}"
