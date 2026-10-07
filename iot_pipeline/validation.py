from dataclasses import dataclass
from numbers import Real

@dataclass(frozen=True)
class Telemetry:
    device_id: str
    temperature: float
    humidity: float
    distance_cm: float
    rssi: int
    sequence: int
    boot_id: int
    uptime_s: int
    sent_at_ms: int

def validate(payload: dict) -> Telemetry:
    required = set(Telemetry.__annotations__)
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if not isinstance(payload["device_id"], str) or not payload["device_id"].strip():
        raise ValueError("device_id must be a non-empty string")
    numeric = required - {"device_id"}
    for key in numeric:
        if isinstance(payload[key], bool) or not isinstance(payload[key], Real):
            raise ValueError(f"{key} must be numeric")
    limits = {"temperature": (-40, 80), "humidity": (0, 100), "distance_cm": (2, 400), "rssi": (-120, 0)}
    for key, (low, high) in limits.items():
        if not low <= float(payload[key]) <= high:
            raise ValueError(f"{key} outside [{low}, {high}]")
    for key in ("sequence", "boot_id", "uptime_s", "sent_at_ms"):
        if int(payload[key]) < 0:
            raise ValueError(f"{key} must be non-negative")
    return Telemetry(str(payload["device_id"]), float(payload["temperature"]),
        float(payload["humidity"]), float(payload["distance_cm"]), int(payload["rssi"]),
        int(payload["sequence"]), int(payload["boot_id"]), int(payload["uptime_s"]),
        int(payload["sent_at_ms"]))

