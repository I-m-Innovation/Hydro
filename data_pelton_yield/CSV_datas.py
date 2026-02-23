# loading json file in CSV_DATA  dictionary
import json
from pathlib import Path


csv_path = Path(__file__).with_name("csv_datas.json")
with csv_path.open("r", encoding="utf-8") as f:
    CSV_DATA = json.load(f)
    
if not isinstance(CSV_DATA, dict):
    raise ValueError("CSV_DATA should be a dictionary loaded from CSV_datas.json")


def save_csv_data(data):
    if not isinstance(data, dict):
        raise ValueError("CSV_DATA must be a dictionary to save")
    with csv_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
