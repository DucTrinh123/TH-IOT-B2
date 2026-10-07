import argparse
import json
import threading
import time
import numpy as np
import pandas as pd
from .config import Settings

SENSORS = ["temperature", "humidity", "distance_cm"]

def transform(frame: pd.DataFrame, interval: str = "1min") -> pd.DataFrame:
    if frame.empty:
        return frame
    data = frame.copy().sort_index()
    data = data[~data.index.duplicated(keep="last")]
    for column in SENSORS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        q1, q3 = data[column].quantile([0.25, 0.75]); iqr = q3 - q1
        if pd.notna(iqr) and iqr > 0:
            data.loc[(data[column] < q1 - 1.5 * iqr) | (data[column] > q3 + 1.5 * iqr), column] = np.nan
    data[SENSORS] = data[SENSORS].interpolate(method="time", limit_direction="both")
    result = data[SENSORS].resample(interval).mean().interpolate(method="time", limit_direction="both")
    for column in SENSORS:
        result[f"{column}_rolling_mean"] = result[column].rolling(3, min_periods=1).mean()
        result[f"{column}_delta"] = result[column].diff().fillna(0)
        std = result[column].std(ddof=0)
        result[f"{column}_zscore"] = 0.0 if not std else (result[column] - result[column].mean()) / std
    return result.dropna()

def process_once(cfg, time_range, interval):
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    import paho.mqtt.client as mqtt
    client = InfluxDBClient(url=cfg.influx_url, token=cfg.influx_token, org=cfg.influx_org)
    query = f'''from(bucket: "{cfg.raw_bucket}")
      |> range(start: {time_range})
      |> filter(fn: (r) => r._measurement == "sensor_telemetry")
      |> filter(fn: (r) => contains(value: r._field, set: ["temperature", "humidity", "distance_cm"]))
      |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")'''
    frames = client.query_api().query_data_frame(query)
    raw = pd.concat(frames, ignore_index=True) if isinstance(frames, list) and frames else frames
    if raw is None or raw.empty:
        print("No raw data found"); client.close(); return 0
    raw["_time"] = pd.to_datetime(raw["_time"], utc=True)
    points = []; dashboard_payloads = []
    for device_id, device_data in raw.groupby("device_id"):
        output = transform(device_data.set_index("_time"), interval)
        for timestamp, row in output.iterrows():
            point = (Point("sensor_features").tag("device_id", str(device_id))
                .tag("pipeline", "iqr-interpolate-resample-zscore"))
            values = {}
            for name, value in row.items():
                point.field(name, float(value))
                values[f"processed_{name}"] = round(float(value), 4)
            points.append(point.time(timestamp.to_pydatetime(), WritePrecision.MS))
            dashboard_payloads.append({"ts": int(timestamp.timestamp() * 1000), "values": values})
    writer = client.write_api(write_options=SYNCHRONOUS)
    writer.write(bucket=cfg.processed_bucket, record=points)
    writer.close(); client.close()
    if cfg.thingsboard_token and dashboard_payloads:
        connected = threading.Event()
        tb = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"iot-processed-{int(time.time())}")
        tb.username_pw_set(cfg.thingsboard_token)
        def on_tb_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                connected.set()
        tb.on_connect = on_tb_connect
        tb.connect(cfg.thingsboard_host, cfg.thingsboard_port, 60); tb.loop_start()
        if not connected.wait(10):
            tb.loop_stop(); tb.disconnect()
            raise RuntimeError("ThingsBoard did not acknowledge MQTT connection")
        # The dashboard needs the newest processed window. Sending the full
        # historical range can exceed ThingsBoard MQTT payload/rate limits.
        latest = dashboard_payloads[-1]
        info = tb.publish("v1/devices/me/telemetry", json.dumps(latest), qos=1)
        info.wait_for_publish(timeout=10)
        tb.loop_stop(); tb.disconnect()
        print("Forwarded latest processed point to ThingsBoard")
    print(f"Stored {len(points)} processed points from {raw['device_id'].nunique()} device(s)")
    return len(points)

def main():
    parser = argparse.ArgumentParser(description="Preprocess IoT time-series data")
    parser.add_argument("--range", default="-24h", dest="time_range")
    parser.add_argument("--interval", default="1min")
    parser.add_argument("--watch", action="store_true",
                        help="run continuously instead of processing once")
    parser.add_argument("--every", type=int, default=60,
                        help="seconds between runs in watch mode (default: 60)")
    args = parser.parse_args(); cfg = Settings()
    if args.every < 10:
        parser.error("--every must be at least 10 seconds")
    while True:
        try:
            print(f"[{pd.Timestamp.now(tz='UTC').isoformat()}] Starting preprocessing")
            process_once(cfg, args.time_range, args.interval)
        except Exception as exc:
            print(f"Preprocessing failed: {type(exc).__name__}: {exc}")
        if not args.watch:
            break
        print(f"Next run in {args.every} seconds (Ctrl+C to stop)")
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            print("Preprocessing stopped")
            break

if __name__ == "__main__": main()

