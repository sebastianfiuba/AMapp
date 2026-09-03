from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATABASE_PATH = DATA_DIR / "mediciones.db"
DATA_DIR.mkdir(exist_ok=True)

APP_TITLE = "AMapp | Mediciones eléctricas"
DATE_FORMAT = "%Y-%m-%d"
