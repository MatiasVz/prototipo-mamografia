from dataclasses import dataclass, field

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from .storage_service import remove_case_storage_directory


@dataclass
class DeleteAccountResult:
    success: bool = False
    password_invalid: bool = False
    # IDs de casos cuyos archivos no se pudieron borrar del disco (la cuenta y
    # los registros si se eliminaron). Sirve para registrar/avisar, no bloquea.
    orphaned_case_ids: list = field(default_factory=list)


def delete_account(user, password, upload_folder):
    """Eliminar definitivamente la cuenta del usuario y todos sus casos.

    Pide la contraseña como confirmacion. Primero borra en base de datos dentro
    de una transaccion (las filas de los casos caen en cascada) y solo despues
    limpia los archivos en disco. Este orden evita dejar registros apuntando a
    archivos ya borrados: si la limpieza de disco falla, a lo sumo quedan
    archivos huerfanos (se registran), nunca registros inconsistentes.
    """
    if not user.check_password(password):
        return DeleteAccountResult(password_invalid=True)

    # Se capturan antes de borrar: tras eliminar el usuario, la relacion ya no existe.
    case_ids = [case.id for case in user.cases]

    try:
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    orphaned = _remove_case_storage(case_ids, upload_folder)
    return DeleteAccountResult(success=True, orphaned_case_ids=orphaned)


def _remove_case_storage(case_ids, upload_folder):
    """Borrar las carpetas de los casos en disco. Best-effort tras el commit."""
    orphaned = []

    for case_id in case_ids:
        try:
            remove_case_storage_directory(case_id, upload_folder)
        except OSError:
            current_app.logger.exception(
                "No se pudieron borrar los archivos del caso id=%s", case_id
            )
            orphaned.append(case_id)

    return orphaned
