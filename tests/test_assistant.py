import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from services.assistant import _local_ai_answer, answer_question


class AssistantRepository:
    def devices(self):
        return pd.DataFrame([{"id": 1, "nombre": "2NDN17", "numero": "17"}])

    def campaigns(self, device_id):
        return pd.DataFrame([{"id": 15, "dispositivo_id": device_id, "numero": "15"}])

    def iv_measurements(self, campaign_id, include_deleted=True):
        return pd.DataFrame([{"id": index, "archivo": f"T{temperature}", "activa": 1}
                             for index, temperature in enumerate((20, 40, 60), start=1)])

    def points(self, measurement_id):
        voltage = np.linspace(0, 1, 101)
        temperature = (20, 40, 60)[measurement_id - 1]
        current = 0.0003 + (voltage - 0.6) * 0.0002 + (temperature - 40) * (voltage - 0.6) * 1e-7
        return pd.DataFrame({"v": voltage, "i": current})


class AssistantTests(unittest.TestCase):
    def test_answers_device_campaign_question_with_local_ztc_analysis(self):
        answer = answer_question(AssistantRepository(), "analiza dispositivo 17, campaña 15")

        self.assertIn("2NDN17, campaña 15", answer)
        self.assertIn("VT=0.6 V", answer)
        self.assertIn("I=300 µA", answer)
        self.assertIn("mínima dispersión", answer)

    @patch("services.assistant.urllib.request.urlopen")
    def test_uses_ollama_when_local_model_is_available(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"message": {"content": "Resumen del análisis."}}).encode()

        answer = _local_ai_answer("analiza el resultado", "VT=0.6 V")

        self.assertEqual(answer, "Resumen del análisis.")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["model"], "qwen2.5:0.5b")


if __name__ == "__main__":
    unittest.main()