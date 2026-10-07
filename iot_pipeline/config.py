import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    mqtt_host: str = os.getenv("MQTT_HOST", "broker.hivemq.com")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "ptit/int14149/b23dcat301/telemetry")
    influx_url: str = os.getenv("INFLUX_URL", "http://localhost:8086")
    influx_token: str = os.getenv("INFLUX_TOKEN", "")
    influx_org: str = os.getenv("INFLUX_ORG", "ptit")
    raw_bucket: str = os.getenv("INFLUX_BUCKET", "iot_raw")
    processed_bucket: str = os.getenv("INFLUX_PROCESSED_BUCKET", "iot_processed")
    thingsboard_host: str = os.getenv("THINGSBOARD_HOST", "mqtt.thingsboard.cloud")
    thingsboard_port: int = int(os.getenv("THINGSBOARD_PORT", "1883"))
    thingsboard_token: str = os.getenv("THINGSBOARD_TOKEN", "")

