import json
import logging
from src.biomarkers.acoustic_biomarker_service import AcousticBiomarkerService
from src.biomarkers.exceptions import AcousticBiomarkerError

# Налаштування логування для відстеження процесів
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# 1. Формуємо словник (dict) згідно з контрактом оркестратора
test_input = {
    "patient_audio_path": "mock_data/testing_audio.wav",
    "segments": [
        {
            "segment_id": 0,
            "start_time": 1.5,
            "end_time": 13.0,
            "latent_response_time": 1.5,
        },
        {
            "segment_id": 1,
            "start_time": 16.0,
            "end_time": 28.0,
            "latent_response_time": 1.1,
        },
        {
            "segment_id": 2,
            "start_time": 31.0,
            "end_time": 43.0,
            "latent_response_time": 0.9,
        },
        {
            "segment_id": 3,
            "start_time": 45.5,
            "end_time": 53.5,
            "latent_response_time": 0.7,
        },
    ],
}

# 2. Ініціалізуємо сервісний клас.
# Для тестування 55-секундного файла явно передаємо window_sec=15.0
service = AcousticBiomarkerService(default_window_sec=15.0)

print("⏳ Запуск фінального аналізу через AcousticBiomarkerService...")

try:
    # 3. Викликаємо головний публічний метод
    result_dict = service.extract_biomarkers(test_input)

    print("\nУспішно! Отримано фінальний dict-вихід:\n")
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))

except AcousticBiomarkerError as e:
    print(f"\nВиникла доменна помилка аналізу біомаркерів: {e}")
except Exception as e:
    print(f"\nНепередбачена системна помилка: {e}")