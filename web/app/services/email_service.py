import json
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


class EmailDeliveryError(Exception):
    """Se eleva cuando el correo no pudo entregarse al servidor SMTP."""


def send_email(to_address, subject, body):
    """Enviar un correo de texto plano usando el backend configurado.

    El backend se elige con MAIL_BACKEND:
      - "console" (por defecto): escribe el correo en el log. Ideal para
        desarrollo y demos: no envia nada real ni requiere credenciales.
      - "smtp": entrega via un servidor SMTP (Gmail dedicado u otro proveedor)
        configurado por variables de entorno.

    Es agnostico al proveedor a proposito, para reutilizarlo tanto en la
    recuperacion de contraseña como en futuros avisos (p. ej. "procesamiento
    listo") sin acoplarse a ningun servicio concreto.
    """
    backend = current_app.config.get("MAIL_BACKEND", "console").strip().lower()

    if backend == "smtp":
        _send_via_smtp(to_address, subject, body)
    elif backend == "brevo":
        _send_via_brevo(to_address, subject, body)
    else:
        _send_via_console(to_address, subject, body)


def _send_via_console(to_address, subject, body):
    current_app.logger.info(
        "[email:console] Para=%s | Asunto=%s\n%s",
        to_address,
        subject,
        body,
    )


def _send_via_smtp(to_address, subject, body):
    config = current_app.config
    host = config.get("MAIL_SMTP_HOST")
    port = int(config.get("MAIL_SMTP_PORT", 587))
    username = config.get("MAIL_SMTP_USERNAME")
    password = config.get("MAIL_SMTP_PASSWORD")
    use_tls = config.get("MAIL_SMTP_USE_TLS", True)
    sender = config.get("MAIL_SENDER") or username

    if not host or not sender:
        raise EmailDeliveryError(
            "Configuracion SMTP incompleta: define MAIL_SMTP_HOST y MAIL_SENDER."
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        # Se traduce a una excepcion propia para que la capa superior la maneje
        # sin exponer detalles internos al usuario.
        raise EmailDeliveryError(str(error)) from error


def _send_via_brevo(to_address, subject, body):
    config = current_app.config
    api_url = config.get("BREVO_API_URL")
    api_key = config.get("BREVO_API_KEY")
    sender_name = config.get("BREVO_SENDER_NAME")
    sender_email = config.get("BREVO_SENDER_EMAIL")

    if not api_url or not api_key or not sender_email:
        raise EmailDeliveryError(
            "Configuracion Brevo incompleta: define API, clave y remitente verificado."
        )

    payload = {
        "sender": {
            "name": sender_name or current_app.config.get("APP_NAME", "Prototipo"),
            "email": sender_email,
        },
        "to": [{"email": to_address}],
        "subject": subject,
        "textContent": body,
    }
    request = Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise EmailDeliveryError(
                    f"Brevo rechazo el correo con estado HTTP {response.status}."
                )
    except HTTPError as error:
        raise EmailDeliveryError(
            f"Brevo rechazo el correo con estado HTTP {error.code}."
        ) from error
    except (OSError, URLError) as error:
        raise EmailDeliveryError(
            "No se pudo conectar con el servicio de correo transaccional."
        ) from error
