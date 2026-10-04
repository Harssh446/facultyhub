from pathlib import Path
from storage import DATA_FILE, save_db, load_db

def ensure_data():
    DATA_FILE.parent.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        save_db({'users':[],'students':[],'attendance':[],'marks':[],'assignments':[],'submissions':[],'questions':[],'quiz_attempts':[],'timetable':[]})
    (DATA_FILE.parent/'uploads').mkdir(exist_ok=True)
