import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def request_json(base_url, path, timeout):
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"User-Agent": "prototipo-deployment-check/1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, payload


def validate_health(base_url, timeout):
    live_status, live = request_json(base_url, "/health/live", timeout)
    ready_status, ready = request_json(base_url, "/health/ready", timeout)
    if live_status != 200 or live.get("status") != "ok":
        raise RuntimeError("La comprobacion de vida no respondio correctamente.")
    if ready_status != 200 or ready.get("status") != "ready":
        raise RuntimeError("La aplicacion no reporto un estado listo.")
    failed_checks = [
        name for name, status in ready.get("checks", {}).items() if status != "ok"
    ]
    if failed_checks:
        raise RuntimeError(
            "Dependencias no disponibles: " + ", ".join(sorted(failed_checks))
        )
    return live.get("version", "unknown"), ready.get("checks", {})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=18)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args(argv)

    last_error = None
    for attempt in range(1, args.attempts + 1):
        try:
            version, checks = validate_health(args.base_url, args.timeout)
            print(f"Web saludable. version={version}")
            print("Dependencias: " + ", ".join(
                f"{name}={status}" for name, status in sorted(checks.items())
            ))
            return 0
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            last_error = exc
            print(f"Intento {attempt}/{args.attempts}: {exc}")
            if attempt < args.attempts:
                time.sleep(args.interval)

    print(f"La validacion web no fue satisfactoria: {last_error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
