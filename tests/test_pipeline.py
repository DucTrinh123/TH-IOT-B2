import unittest
import pandas as pd
from iot_pipeline.validation import validate
from iot_pipeline.preprocess import transform

VALID = {"device_id":"esp32-test", "temperature":25, "humidity":50, "distance_cm":100,
         "rssi":-60, "sequence":1, "boot_id":2, "uptime_s":5, "sent_at_ms":1700000000000}

class PipelineTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate(VALID).temperature, 25)
        with self.assertRaises(ValueError): validate({**VALID, "humidity": 101})
    def test_transform_creates_features(self):
        index = pd.date_range("2026-01-01", periods=5, freq="30s", tz="UTC")
        frame = pd.DataFrame({"temperature":[20, 21, 1000, 23, 24],
            "humidity":[40, 41, 42, 43, 44], "distance_cm":[100, 101, 102, 103, 104]}, index=index)
        result = transform(frame, "1min")
        self.assertIn("temperature_rolling_mean", result)
        self.assertLess(result["temperature"].max(), 100)

if __name__ == "__main__": unittest.main()

