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


class FileRole:
    """Roles de los archivos asociados a un caso (filas de la tabla files)."""

    ORIGINAL = "original"
    ROI = "roi"
    SIMULATION_INPUT = "simulation_input"
    RESULTS_DIR = "results_dir"
    METRICS = "metrics"
    DENSITY_MAP = "density_map"
    LOG = "log"


def _file_property(role, field):
    """Crear una propiedad de compatibilidad que lee/escribe un campo de la fila
    de `files` con el rol indicado, para no cambiar la interfaz que usa el resto
    del codigo tras normalizar el almacenamiento de archivos."""

    def getter(self):
        return self._get_file_field(role, field)

    def setter(self, value):
        self._set_file_field(role, field, value)

    return property(getter, setter)


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
    files = db.relationship(
        "File",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="File.id",
    )

    # Propiedades de compatibilidad: la informacion de archivos vive ahora en la
    # tabla `files` (una fila por archivo, identificada por su rol). Estas
    # propiedades mantienen la misma interfaz (case.original_file_path, etc.) para
    # que el resto del codigo y las plantillas no cambien.
    original_filename = _file_property(FileRole.ORIGINAL, "filename")
    original_file_path = _file_property(FileRole.ORIGINAL, "path")
    file_type = _file_property(FileRole.ORIGINAL, "file_type")
    file_size_bytes = _file_property(FileRole.ORIGINAL, "size_bytes")
    roi_filename = _file_property(FileRole.ROI, "filename")
    roi_file_path = _file_property(FileRole.ROI, "path")
    roi_file_type = _file_property(FileRole.ROI, "file_type")
    roi_size_bytes = _file_property(FileRole.ROI, "size_bytes")
    simulation_input_filename = _file_property(FileRole.SIMULATION_INPUT, "filename")
    simulation_input_file_path = _file_property(FileRole.SIMULATION_INPUT, "path")
    simulation_input_file_type = _file_property(FileRole.SIMULATION_INPUT, "file_type")
    simulation_input_size_bytes = _file_property(FileRole.SIMULATION_INPUT, "size_bytes")
    simulation_results_path = _file_property(FileRole.RESULTS_DIR, "path")
    simulation_metrics_file_path = _file_property(FileRole.METRICS, "path")
    simulation_density_map_file_path = _file_property(FileRole.DENSITY_MAP, "path")
    simulation_log_file_path = _file_property(FileRole.LOG, "path")

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
        setattr(self, "status", status)
        setattr(self, "error_message", error_message)
        setattr(self, "user_id", user_id)
        # Los campos de archivo se enrutan a la tabla files via las propiedades.
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

    def _get_file(self, role):
        for stored_file in self.files:
            if stored_file.role == role:
                return stored_file
        return None

    def _get_file_field(self, role, field):
        stored_file = self._get_file(role)
        return getattr(stored_file, field) if stored_file is not None else None

    def _set_file_field(self, role, field, value):
        stored_file = self._get_file(role)

        if stored_file is None:
            # No creamos una fila vacia para un valor nulo (p. ej. ROI ausente).
            if value is None:
                return
            stored_file = File(role=role)
            self.files.append(stored_file)

        setattr(stored_file, field, value)

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


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    case_id = db.Column(
        db.Integer,
        db.ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(db.String(40), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    path = db.Column(db.String(500), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)

    case = db.relationship("Case", back_populates="files")

    def __init__(
        self,
        role="",
        filename=None,
        path=None,
        file_type=None,
        size_bytes=None,
        case_id=None,
    ):
        setattr(self, "role", role)
        setattr(self, "filename", filename)
        setattr(self, "path", path)
        setattr(self, "file_type", file_type)
        setattr(self, "size_bytes", size_bytes)
        setattr(self, "case_id", case_id)

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "role": self.role,
            "filename": self.filename,
            "path": self.path,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<File id={self.id} case_id={self.case_id} role={self.role}>"


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
