from datetime import datetime, timezone

from .extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class InputMode:
    MAMMOGRAM = "mamografia_completa"
    ROI = "roi_recortada"

    @classmethod
    def values(cls):
        return (cls.MAMMOGRAM, cls.ROI)


class CaseStatus:
    REGISTERED = "registrado"
    ROI_CONFIRMED = "roi_confirmada"
    PENDING = "pendiente"
    PROCESSING = "procesando"
    COMPLETED = "completado"
    ERROR = "error"
    NOTIFIED = "notificado"

    @classmethod
    def values(cls):
        return (
            cls.REGISTERED,
            cls.ROI_CONFIRMED,
            cls.PENDING,
            cls.PROCESSING,
            cls.COMPLETED,
            cls.ERROR,
            cls.NOTIFIED,
        )


class Case(db.Model):
    __tablename__ = "cases"
    __table_args__ = (
        db.CheckConstraint(
            "input_mode IN ('mamografia_completa', 'roi_recortada')",
            name="ck_cases_input_mode",
        ),
        db.CheckConstraint(
            "status IN ('registrado', 'roi_confirmada', 'pendiente', 'procesando', 'completado', 'error', 'notificado')",
            name="ck_cases_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    input_mode = db.Column(
        db.String(40),
        nullable=False,
        default=InputMode.MAMMOGRAM,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    original_file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=False)
    roi_filename = db.Column(db.String(255), nullable=True)
    roi_file_path = db.Column(db.String(500), nullable=True)
    roi_file_type = db.Column(db.String(50), nullable=True)
    roi_size_bytes = db.Column(db.BigInteger, nullable=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default=CaseStatus.REGISTERED,
    )
    error_message = db.Column(db.Text, nullable=True)

    def __init__(
        self,
        input_mode=InputMode.MAMMOGRAM,
        original_filename="",
        original_file_path="",
        file_type="",
        file_size_bytes=0,
        roi_filename=None,
        roi_file_path=None,
        roi_file_type=None,
        roi_size_bytes=None,
        status=CaseStatus.REGISTERED,
        error_message=None,
    ):
        setattr(self, "input_mode", input_mode)
        setattr(self, "original_filename", original_filename)
        setattr(self, "original_file_path", original_file_path)
        setattr(self, "file_type", file_type)
        setattr(self, "file_size_bytes", file_size_bytes)
        setattr(self, "roi_filename", roi_filename)
        setattr(self, "roi_file_path", roi_file_path)
        setattr(self, "roi_file_type", roi_file_type)
        setattr(self, "roi_size_bytes", roi_size_bytes)
        setattr(self, "status", status)
        setattr(self, "error_message", error_message)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "input_mode": self.input_mode,
            "original_filename": self.original_filename,
            "original_file_path": self.original_file_path,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "roi_filename": self.roi_filename,
            "roi_file_path": self.roi_file_path,
            "roi_file_type": self.roi_file_type,
            "roi_size_bytes": self.roi_size_bytes,
            "status": self.status,
            "error_message": self.error_message,
        }

    def __repr__(self):
        return f"<Case id={self.id} status={self.status}>"
