import json
import logging
import time
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from .config import Settings
from .validation import validate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collector")
cfg = Settings()
influx = InfluxDBClient(url=cfg.influx_url, token=cfg.influx_token, org=cfg.influx_org)
writer = influx.write_api(write_options=SYNCHRONOUS)
seen_queue = deque(maxlen=10000)
seen = set()
tb_client = None
counters = {"accepted": 0, "rejected": 0, "duplicate": 0}
started_at = time.monotonic()

def remember(key: tuple) -> bool:
    if key in seen:
        return False
    if len(seen_queue) == seen_queue.maxlen:
        seen.discard(seen_queue[0])
    seen_queue.append(key)
    seen.add(key)
    return True

def setup_thingsboard():
    global tb_client
    if not cfg.thingsboard_token:
        log.warning("THINGSBOARD_TOKEN is empty; forwarding disabled")
        return
    tb_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"tb-forwarder-{int(time.time())}")
    tb_client.username_pw_set(cfg.thingsboard_token)
    tb_client.connect(cfg.thingsboard_host, cfg.thingsboard_port, 60)
    tb_client.loop_start()

def write_pipeline_metric(device_id, received_ms, payload_bytes, ingest_ms=-1,
                          db_write_ms=-1, total_ms=-1, status="accepted"):
    counters[status] += 1
    elapsed = max(time.monotonic() - started_at, 0.001)
    metric = (Point("pipeline_metrics")
        .tag("device_id", device_id).tag("status", status)
        .field("payload_bytes", int(payload_bytes))
        .field("ingest_latency_ms", float(ingest_ms))
        .field("db_write_ms", float(db_write_ms))
        .field("processing_total_ms", float(total_ms))
        .field("accepted_count", counters["accepted"])
        .field("rejected_count", counters["rejected"])
        .field("duplicate_count", counters["duplicate"])
        .field("throughput_msg_s", counters["accepted"] / elapsed)
        .time(received_ms, WritePrecision.MS))
    writer.write(bucket=cfg.raw_bucket, record=metric)
    return {
        "db_write_ms": round(float(db_write_ms), 2),
        "processing_total_ms": round(float(total_ms), 2),
        "throughput_msg_s": round(counters["accepted"] / elapsed, 4),
        "accepted_count": counters["accepted"],
        "rejected_count": counters["rejected"],
        "duplicate_count": counters["duplicate"],
    }

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        log.error("MQTT connect failed: %s", reason_code)
        return
    client.subscribe(cfg.mqtt_topic, qos=1)
    log.info("Subscribed to %s", cfg.mqtt_topic)

def on_message(client, userdata, message):
    received_ms = int(time.time() * 1000)
    processing_started = time.perf_counter()
    payload_bytes = len(message.payload)
    device_id = "unknown"
    try:
        raw = json.loads(message.payload.decode("utf-8"))
        item = validate(raw)
        device_id = item.device_id
        if not remember((item.device_id, item.boot_id, item.sequence)):
            log.warning("Duplicate ignored: %s/%s/%s", item.device_id, item.boot_id, item.sequence)
            write_pipeline_metric(device_id, received_ms, payload_bytes, status="duplicate")
            return
        latency_ms = max(0, received_ms - item.sent_at_ms) if item.sent_at_ms else -1
        timestamp = datetime.fromtimestamp(item.sent_at_ms / 1000, timezone.utc) if item.sent_at_ms else datetime.now(timezone.utc)
        point = (Point("sensor_telemetry").tag("device_id", item.device_id).tag("source", "esp32")
            .field("temperature", item.temperature).field("humidity", item.humidity)
            .field("distance_cm", item.distance_cm).field("rssi", item.rssi)
            .field("sequence", item.sequence).field("boot_id", item.boot_id)
            .field("uptime_s", item.uptime_s).field("latency_ms", latency_ms)
            .time(timestamp, WritePrecision.MS))
        write_started = time.perf_counter()
        writer.write(bucket=cfg.raw_bucket, record=point)
        db_write_ms = (time.perf_counter() - write_started) * 1000
        if tb_client:
            forwarded = dict(raw, latency_ms=latency_ms)
            info = tb_client.publish("v1/devices/me/telemetry", json.dumps(forwarded), qos=1)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                info.wait_for_publish(timeout=5)
            else:
                log.error("ThingsBoard raw publish error %s", info.rc)
        total_ms = (time.perf_counter() - processing_started) * 1000
        metric_values = write_pipeline_metric(
            device_id, received_ms, payload_bytes, latency_ms, db_write_ms, total_ms)
        if tb_client:
            info = tb_client.publish(
                "v1/devices/me/telemetry", json.dumps(metric_values), qos=1)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                info.wait_for_publish(timeout=5)
            else:
                log.error("ThingsBoard metric publish error %s", info.rc)
        log.info("Stored/forwarded %s seq=%s ingest=%.1fms db=%.1fms total=%.1fms",
                 item.device_id, item.sequence, latency_ms, db_write_ms, total_ms)
    except Exception as exc:
        try:
            write_pipeline_metric(device_id, received_ms, payload_bytes,
                                  total_ms=(time.perf_counter() - processing_started) * 1000,
                                  status="rejected")
        except Exception as metric_exc:
            log.error("Cannot store rejection metric: %s", metric_exc)
        log.warning("Rejected payload: %s", exc)

def main():
    setup_thingsboard()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"iot-lab-collector-{int(time.time())}")
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(1, 30)
    client.connect(cfg.mqtt_host, cfg.mqtt_port, 60)
    try:
        client.loop_forever()
    finally:
        if tb_client:
            tb_client.loop_stop(); tb_client.disconnect()
        writer.close(); influx.close()

if __name__ == "__main__":
    main()

