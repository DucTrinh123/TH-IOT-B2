# Bài thực hành số 2 - Thu thập, lưu trữ và tiền xử lý dữ liệu IoT

Hệ thống đọc nhiệt độ, độ ẩm và khoảng cách từ ESP32/Wokwi; truyền dữ liệu qua MQTT;
kiểm tra, lưu trữ và tiền xử lý bằng Python + InfluxDB; sau đó hiển thị dữ liệu raw và
processed trên ThingsBoard.

## 1. Kiến trúc hệ thống

```text
DHT22 + HC-SR04
        ↓
ESP32 / Wokwi
        ↓ JSON mỗi 5 giây
HiveMQ MQTT Broker
        ↓ subscribe
Python Collector
        ├── Validate và chống trùng
        ├── InfluxDB / iot_raw
        └── ThingsBoard / dữ liệu real-time

InfluxDB / iot_raw
        ↓
Python Preprocessing
        ├── InfluxDB / iot_processed
        └── ThingsBoard / dữ liệu processed_*
```

- MQTT broker: `broker.hivemq.com:1883`
- Topic: `ptit/int14149/b23dcat301/telemetry`
- ThingsBoard topic: `v1/devices/me/telemetry`
- Sơ đồ chi tiết: [`docs/architecture.md`](docs/architecture.md)
- Schema chi tiết: [`docs/schema.md`](docs/schema.md)

## 2. Thành phần sử dụng

- ESP32 DevKit V1 mô phỏng bằng Wokwi.
- DHT22 đo nhiệt độ, độ ẩm; HC-SR04 đo khoảng cách.
- Python 3.11, Paho MQTT và Pandas.
- InfluxDB 2.7 chạy bằng Docker.
- ThingsBoard Cloud và Streamlit làm dashboard.
- PlatformIO để build firmware.

## 3. Chuẩn bị môi trường

### 3.1. Tạo file cấu hình

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay token thiết bị ThingsBoard:

```env
THINGSBOARD_TOKEN=access_token_cua_thiet_bi
```

Đồng thời đặt `INFLUX_ADMIN_PASSWORD` và `INFLUX_TOKEN` thành các giá trị bí mật đủ
mạnh; không giữ nguyên placeholder trong `.env.example`.

Không commit `.env` vì file chứa thông tin xác thực.

### 3.2. Khởi động InfluxDB

```powershell
docker compose up -d
docker compose ps
```

Thông tin truy cập:

```text
URL:          http://localhost:8086
Username:     giá trị INFLUX_ADMIN_USERNAME trong .env
Password:     giá trị INFLUX_ADMIN_PASSWORD trong .env
Organization: ptit
Raw bucket:   iot_raw
```

### 3.3. Tạo môi trường Python riêng

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Không nên dùng Python toàn cục vì có thể xung đột phiên bản thư viện.

### 3.4. Tạo bucket processed

```powershell
.\.venv\Scripts\python.exe scripts/setup_influx.py
```

Bucket `iot_processed` có retention 30 ngày. Bucket `iot_raw` có retention 7 ngày và
được tạo bởi Docker Compose.

## 4. Chạy toàn bộ hệ thống

Mở ba terminal tại thư mục gốc của dự án (thư mục chứa `README.md`).

### Terminal 1 - Collector

```powershell
.\.venv\Scripts\python.exe -m iot_pipeline.collector
```

Kết quả mong đợi:

```text
Subscribed to ptit/int14149/b23dcat301/telemetry
Stored/forwarded esp32-b23dcat301 seq=... ingest=...ms db=...ms total=...ms
```

Collector chạy liên tục để subscribe MQTT, validate dữ liệu, loại bản tin trùng, ghi
InfluxDB và forward dữ liệu raw cùng metric lên ThingsBoard.

### Terminal 2 - Preprocessing liên tục

```powershell
.\.venv\Scripts\python.exe -m iot_pipeline.preprocess --range=-2h --interval=1min --watch --every=60
```

Chương trình chạy lại mỗi 60 giây, ghi kết quả vào InfluxDB và gửi cửa sổ processed
mới nhất lên ThingsBoard. Dừng bằng `Ctrl+C`.

Nếu chỉ muốn xử lý một lần:

```powershell
.\.venv\Scripts\python.exe -m iot_pipeline.preprocess --range=-24h --interval=1min
```

### Terminal 3 - Firmware và Wokwi

```powershell
pio run
```

Sau khi build thành công, chọn:

```text
F1 → Wokwi: Start Simulator
```

Serial Monitor phải có:

```text
Connecting WiFi... connected
Connecting MQTT... connected
{...} | publish=OK
```

Nếu Wokwi báo không tìm thấy firmware, chạy lại `pio run`. Hai file cần có:

```text
.pio/build/esp32dev/firmware.bin
.pio/build/esp32dev/firmware.elf
```

### Terminal 4 - Streamlit dashboard

Nếu cần dashboard đúng theo yêu cầu Grafana hoặc Streamlit của đề, chạy:

```powershell
.\.venv\Scripts\streamlit.exe run streamlit_app.py
```

Dashboard Streamlit đọc trực tiếp từ InfluxDB, hiển thị dữ liệu raw trong `iot_raw`,
dữ liệu đã xử lý trong `iot_processed` và metric hiệu năng của collector.

## 5. Định dạng dữ liệu MQTT

Ví dụ payload từ ESP32:

```json
{
  "device_id": "esp32-b23dcat301",
  "temperature": 25.0,
  "humidity": 50.0,
  "distance_cm": 100.0,
  "rssi": -60,
  "sequence": 1,
  "boot_id": 123456,
  "uptime_s": 5,
  "sent_at_ms": 1790670000000
}
```

| Trường | Miền hợp lệ |
|---|---:|
| `temperature` | -40 đến 80 °C |
| `humidity` | 0 đến 100 %RH |
| `distance_cm` | 2 đến 400 cm |
| `rssi` | -120 đến 0 dBm |

## 6. Schema InfluxDB

### Dữ liệu raw

- Bucket: `iot_raw`, retention 7 ngày.
- Measurement: `sensor_telemetry`.
- Tags: `device_id`, `source`.
- Fields: `temperature`, `humidity`, `distance_cm`, `rssi`, `sequence`, `boot_id`,
  `uptime_s`, `latency_ms`.

### Metric pipeline

- Bucket: `iot_raw`.
- Measurement: `pipeline_metrics`.
- Tags: `device_id`, `status`.
- Fields: `db_write_ms`, `processing_total_ms`, `throughput_msg_s`, `payload_bytes`,
  `accepted_count`, `rejected_count`, `duplicate_count`.

### Dữ liệu processed

- Bucket: `iot_processed`, retention 30 ngày.
- Measurement: `sensor_features`.
- Tags: `device_id`, `pipeline`.
- Fields cho từng cảm biến: giá trị sạch, `rolling_mean`, `delta`, `zscore`.

## 7. Quy trình tiền xử lý

Mỗi thiết bị được xử lý riêng:

1. Đọc dữ liệu raw theo khoảng thời gian.
2. Sắp xếp và loại timestamp trùng.
3. Chuyển giá trị không hợp lệ thành `NaN`.
4. Phát hiện outlier bằng IQR.
5. Chuyển outlier thành `NaN` và nội suy theo thời gian.
6. Resampling trung bình theo cửa sổ 1 phút.
7. Tạo rolling mean 3 cửa sổ và delta.
8. Chuẩn hóa bằng Z-score.
9. Lưu vào `iot_processed/sensor_features`.
10. Forward điểm processed mới nhất lên ThingsBoard với tiền tố `processed_`.

## 8. Dashboard ThingsBoard / Streamlit

Dashboard tối thiểu đúng yêu cầu bài:

### Giá trị real-time

- Value Card: `temperature` - °C.
- Value Card: `humidity` - %RH.
- Gauge hoặc Value Card: `distance_cm` - cm.

### Biểu đồ real-time

Tạo Time Series Chart gồm:

```text
temperature
humidity
distance_cm
```

Chọn cửa sổ `Last 10 minutes` hoặc `Last 30 minutes`.

### So sánh raw và processed

Tạo Time Series Chart gồm:

```text
temperature
processed_temperature
processed_temperature_rolling_mean
```

Có thể tạo thêm biểu đồ tương tự cho `humidity` và `distance_cm`. Không bắt buộc đưa
`delta` và `zscore` lên dashboard chính. Xem thêm
[`docs/thingsboard-dashboard.md`](docs/thingsboard-dashboard.md).

## 9. Độ trễ và hiệu năng

| Key | Ý nghĩa |
|---|---|
| `db_write_ms` | Thời gian ghi đồng bộ vào InfluxDB |
| `processing_total_ms` | Tổng thời gian collector xử lý một bản tin |
| `throughput_msg_s` | Thông lượng bản tin trung bình |
| `accepted_count` | Số bản tin hợp lệ trong phiên collector |
| `rejected_count` | Số bản tin bị từ chối |
| `duplicate_count` | Số bản tin trùng |

Xuất báo cáo Markdown và CSV:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_performance.py --range=-24h
```

Kết quả nằm trong `outputs/performance_report.md` và
`outputs/performance_report.csv`.

### Lưu ý về `latency_ms` trên Wokwi

`latency_ms` được tính từ timestamp ESP32 đến lúc collector nhận. Đồng hồ Wokwi có thể
chạy chậm hơn đồng hồ Windows, khiến giá trị tăng dần và không phản ánh độ trễ MQTT
thực tế. Khi đánh giá mô phỏng, ưu tiên `db_write_ms` và `processing_total_ms`. Khi
triển khai ESP32 thật, cần đồng bộ NTP trên thiết bị và gateway trước khi đo end-to-end.

## 10. Kiểm tra hệ thống

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hệ thống hoạt động đúng khi:

- `pio run` kết thúc với `SUCCESS`.
- Serial Monitor hiển thị `publish=OK`.
- Collector hiển thị `Stored/forwarded` và sequence tăng.
- `iot_raw/sensor_telemetry` có dữ liệu mới.
- `iot_raw/pipeline_metrics` có metric hiệu năng.
- `iot_processed/sensor_features` có dữ liệu đã xử lý.
- ThingsBoard có các key raw, metric và `processed_*`.
- `rejected_count` và `duplicate_count` bình thường bằng 0.

## 11. Xử lý lỗi thường gặp

### `ModuleNotFoundError`

Luôn chạy bằng Python trong `.venv`:

```powershell
.\.venv\Scripts\python.exe -m iot_pipeline.collector
```

### ThingsBoard không có dữ liệu

- Kiểm tra `THINGSBOARD_TOKEN` trong `.env`.
- Khởi động lại collector sau khi sửa `.env`.
- Kiểm tra terminal collector có lỗi kết nối hay không.

### Processed không cập nhật

Kiểm tra preprocessing vẫn đang chạy với `--watch`. Raw cập nhật mỗi 5 giây, còn
processed cập nhật mỗi 60 giây.

### `source` hoặc `status` là `undefined` trong InfluxDB

Hai measurement có schema tag khác nhau. `sensor_telemetry` có `source`, còn
`pipeline_metrics` có `status`. Filter từng measurement thay vì hiển thị chung.

### `sequence` hiển thị số thập phân

Dashboard đang dùng phép `mean`. Với `sequence` và counter, chọn aggregation
`Last/Latest`.

## 12. Bảo mật và giới hạn

- MQTT 1883 không mã hóa; triển khai thật nên dùng TLS 8883.
- Public HiveMQ phù hợp demo nhưng không cam kết SLA hoặc tính riêng tư.
- Device token chỉ gửi telemetry, không có quyền quản trị dashboard.
- HC-SR04 thật cần chia áp ECHO từ 5 V xuống 3,3 V trước khi nối ESP32.
- Bộ chống trùng lưu trong RAM và reset khi collector khởi động lại.

## 13. Cấu trúc dự án

```text
sketch.ino                      Firmware ESP32
diagram.json                    Mạch Wokwi
platformio.ini                  Cấu hình PlatformIO
docker-compose.yml              InfluxDB 2.7
iot_pipeline/collector.py       MQTT collector
iot_pipeline/validation.py      Validate telemetry
iot_pipeline/preprocess.py      Tiền xử lý batch/watch
scripts/setup_influx.py         Tạo bucket processed
scripts/evaluate_performance.py Xuất báo cáo hiệu năng
docs/architecture.md            Sơ đồ kiến trúc
docs/schema.md                  Mô tả schema
output/                         Báo cáo Word
```

