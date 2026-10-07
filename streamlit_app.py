import pandas as pd
import streamlit as st
from influxdb_client import InfluxDBClient

from iot_pipeline.config import Settings


SENSORS = ["temperature", "humidity", "distance_cm"]


@st.cache_data(ttl=10)
def query_frame(bucket: str, measurement: str, fields: list[str], time_range: str) -> pd.DataFrame:
    cfg = Settings()
    field_list = ", ".join(f'"{field}"' for field in fields)
    query = f'''from(bucket: "{bucket}")
      |> range(start: {time_range})
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> filter(fn: (r) => contains(value: r._field, set: [{field_list}]))
      |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
      |> sort(columns: ["_time"])'''
    with InfluxDBClient(url=cfg.influx_url, token=cfg.influx_token, org=cfg.influx_org) as client:
        frames = client.query_api().query_data_frame(query)
    if isinstance(frames, list):
        frames = [frame for frame in frames if not frame.empty]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        data = frames if frames is not None else pd.DataFrame()
    if data.empty:
        return data
    data["_time"] = pd.to_datetime(data["_time"], utc=True)
    return data.set_index("_time")


def latest_metric(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame:
        return "N/A"
    value = pd.to_numeric(frame[column], errors="coerce").dropna()
    if value.empty:
        return "N/A"
    return f"{value.iloc[-1]:.2f}"


st.set_page_config(page_title="IoT Realtime Dashboard", layout="wide")
st.title("IoT Realtime Dashboard")

time_range = st.sidebar.selectbox(
    "Time range",
    ["-15m", "-1h", "-6h", "-24h"],
    index=1,
)
auto_refresh = st.sidebar.toggle("Auto refresh", value=True)
if auto_refresh:
    st.sidebar.caption("Refresh trinh duyet de cap nhat neu Streamlit ban hien tai khong tu refresh.")

raw = query_frame("iot_raw", "sensor_telemetry", SENSORS + ["latency_ms", "rssi"], time_range)
processed_fields = []
for sensor in SENSORS:
    processed_fields.extend([sensor, f"{sensor}_rolling_mean", f"{sensor}_delta", f"{sensor}_zscore"])
processed = query_frame("iot_processed", "sensor_features", processed_fields, time_range)
metrics = query_frame(
    "iot_raw",
    "pipeline_metrics",
    ["db_write_ms", "processing_total_ms", "throughput_msg_s", "accepted_count", "rejected_count", "duplicate_count"],
    time_range,
)

st.subheader("Latest raw telemetry")
cols = st.columns(4)
cols[0].metric("Temperature", latest_metric(raw, "temperature"), "°C")
cols[1].metric("Humidity", latest_metric(raw, "humidity"), "%RH")
cols[2].metric("Distance", latest_metric(raw, "distance_cm"), "cm")
cols[3].metric("Latency", latest_metric(raw, "latency_ms"), "ms")

if raw.empty:
    st.info("Chua co du lieu raw trong khoang thoi gian da chon.")
else:
    st.line_chart(raw[[column for column in SENSORS if column in raw]])

st.subheader("Processed telemetry")
if processed.empty:
    st.info("Chua co du lieu processed. Hay chay preprocess truoc.")
else:
    sensor = st.selectbox("Sensor", SENSORS)
    columns = [sensor, f"{sensor}_rolling_mean"]
    available = [column for column in columns if column in processed]
    if available:
        st.line_chart(processed[available])
    feature_cols = [column for column in [f"{sensor}_delta", f"{sensor}_zscore"] if column in processed]
    if feature_cols:
        st.dataframe(processed[feature_cols].tail(20), use_container_width=True)

st.subheader("Pipeline performance")
if metrics.empty:
    st.info("Chua co pipeline metrics trong khoang thoi gian da chon.")
else:
    cols = st.columns(3)
    cols[0].metric("DB write", latest_metric(metrics, "db_write_ms"), "ms")
    cols[1].metric("Processing", latest_metric(metrics, "processing_total_ms"), "ms")
    cols[2].metric("Throughput", latest_metric(metrics, "throughput_msg_s"), "msg/s")
    chart_cols = [column for column in ["db_write_ms", "processing_total_ms"] if column in metrics]
    if chart_cols:
        st.line_chart(metrics[chart_cols])
