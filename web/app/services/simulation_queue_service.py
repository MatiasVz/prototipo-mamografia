from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from ..extensions import db
from ..models import CaseStatus


class SimulationQueueError(RuntimeError):
    pass


@dataclass
class QueuedSimulationJob:
    case_id: int
    queue_name: str
    already_queued: bool = False


def enqueue_case_simulation(case, app_config):
    _ensure_case_can_be_queued(case)

    queue_name = app_config["SIMULATION_QUEUE_NAME"]

    if case.status == CaseStatus.PENDING:
        return QueuedSimulationJob(case.id, queue_name, already_queued=True)

    case.status = CaseStatus.PENDING
    case.error_message = None
    case.simulation_results_path = None
    case.simulation_metrics_file_path = None
    case.simulation_density_map_file_path = None
    case.simulation_log_file_path = None
    db.session.commit()

    try:
        _get_redis_client(app_config).rpush(queue_name, str(case.id))
    except RedisError as exc:
        case.status = CaseStatus.ERROR
        case.error_message = "No se pudo encolar la simulacion en Redis."
        db.session.commit()
        raise SimulationQueueError(case.error_message) from exc

    return QueuedSimulationJob(case.id, queue_name)


def pop_queued_case_id(app_config, timeout_seconds=5):
    queue_name = app_config["SIMULATION_QUEUE_NAME"]

    try:
        queued_item = _get_redis_client(app_config).blpop(
            queue_name,
            timeout=max(1, int(timeout_seconds)),
        )
    except RedisError as exc:
        raise SimulationQueueError("No se pudo leer la cola Redis.") from exc

    if queued_item is None:
        return None

    _queue_name, raw_case_id = queued_item

    try:
        return int(raw_case_id)
    except (TypeError, ValueError) as exc:
        raise SimulationQueueError(
            f"La cola contiene un identificador de caso invalido: {raw_case_id!r}."
        ) from exc


def _ensure_case_can_be_queued(case):
    if not case.simulation_input_file_path:
        raise SimulationQueueError(
            "El caso no tiene archivo PGM preparado para la simulacion."
        )

    if case.status == CaseStatus.PROCESSING:
        raise SimulationQueueError("El caso ya se encuentra en procesamiento.")

    if case.status == CaseStatus.COMPLETED:
        raise SimulationQueueError("El caso ya cuenta con resultados de simulacion.")


def _get_redis_client(app_config):
    return Redis.from_url(app_config["REDIS_URL"], decode_responses=True)
