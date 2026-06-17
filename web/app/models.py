from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

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
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
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
    simulation_input_filename = db.Column(db.String(255), nullable=True)
    simulation_input_file_path = db.Column(db.String(500), nullable=True)
    simulation_input_file_type = db.Column(db.String(50), nullable=True)
    simulation_input_size_bytes = db.Column(db.BigInteger, nullable=True)
    simulation_results_path = db.Column(db.String(500), nullable=True)
    simulation_metrics_file_path = db.Column(db.String(500), nullable=True)
    simulation_density_map_file_path = db.Column(db.String(500), nullable=True)
    simulation_log_file_path = db.Column(db.String(500), nullable=True)
    status = db.Column(
        db.String(30),
        nullable=False,
        default=CaseStatus.REGISTERED,
    )
    error_message = db.Column(db.Text, nullable=True)
    user = db.relationship(
        "User",
        backref=db.backref("cases", cascade="all, delete-orphan"),
    )

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
        simulation_input_filename=None,
        simulation_input_file_path=None,
        simulation_input_file_type=None,
        simulation_input_size_bytes=None,
        simulation_results_path=None,
        simulation_metrics_file_path=None,
        simulation_density_map_file_path=None,
        simulation_log_file_path=None,
        status=CaseStatus.REGISTERED,
        error_message=None,
        user_id=None,
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
        setattr(self, "simulation_input_filename", simulation_input_filename)
        setattr(self, "simulation_input_file_path", simulation_input_file_path)
        setattr(self, "simulation_input_file_type", simulation_input_file_type)
        setattr(self, "simulation_input_size_bytes", simulation_input_size_bytes)
        setattr(self, "simulation_results_path", simulation_results_path)
        setattr(self, "simulation_metrics_file_path", simulation_metrics_file_path)
        setattr(self, "simulation_density_map_file_path", simulation_density_map_file_path)
        setattr(self, "simulation_log_file_path", simulation_log_file_path)
        setattr(self, "status", status)
        setattr(self, "error_message", error_message)
        setattr(self, "user_id", user_id)

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
            "simulation_input_filename": self.simulation_input_filename,
            "simulation_input_file_path": self.simulation_input_file_path,
            "simulation_input_file_type": self.simulation_input_file_type,
            "simulation_input_size_bytes": self.simulation_input_size_bytes,
            "simulation_results_path": self.simulation_results_path,
            "simulation_metrics_file_path": self.simulation_metrics_file_path,
            "simulation_density_map_file_path": self.simulation_density_map_file_path,
            "simulation_log_file_path": self.simulation_log_file_path,
            "status": self.status,
            "error_message": self.error_message,
            "user_id": self.user_id,
        }

    def __repr__(self):
        return f"<Case id={self.id} status={self.status}>"


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("email", name="uq_users_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def __init__(self, email="", name=None):
        setattr(self, "email", email)
        setattr(self, "name", name)

    @staticmethod
    def normalize_email(email):
        return (email or "").strip().lower()

    def set_password(self, password):
        setattr(self, "password_hash", generate_password_hash(password))

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "email": self.email,
            "name": self.name,
        }

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"
