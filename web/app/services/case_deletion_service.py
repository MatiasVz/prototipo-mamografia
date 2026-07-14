from dataclasses import dataclass

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import CaseStatus
from .storage_service import remove_case_storage_directory


ACTIVE_PROCESSING_STATUSES = frozenset(
    {
        CaseStatus.PENDING,
        CaseStatus.PROCESSING,
    }
)


@dataclass(frozen=True)
class CaseDeletionResult:
    case_id: int
    deleted: bool = False
    processing_active: bool = False
    storage_cleanup_failed: bool = False


def can_delete_case(case):
    """Return whether a case can be removed without racing an active worker."""
    return case.status not in ACTIVE_PROCESSING_STATUSES


def delete_case(case, upload_folder):
    """Delete a case and attempt to remove all files stored for it.

    Database rows are committed first because the ORM and database cascades remove
    the related files and result rows together. Storage cleanup is then best-effort:
    a disk failure can leave an orphaned directory, but never a database case that
    points to files that no longer exist.
    """
    if not can_delete_case(case):
        return CaseDeletionResult(case_id=case.id, processing_active=True)

    case_id = case.id
    user_id = case.user_id

    try:
        db.session.delete(case)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    try:
        remove_case_storage_directory(
            case_id,
            upload_folder,
            user_id=user_id,
        )
    except OSError:
        current_app.logger.exception(
            "El caso %s fue eliminado de la base de datos, pero no se pudo limpiar su almacenamiento.",
            case_id,
        )
        return CaseDeletionResult(
            case_id=case_id,
            deleted=True,
            storage_cleanup_failed=True,
        )

    return CaseDeletionResult(case_id=case_id, deleted=True)
