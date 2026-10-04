import json, os, threading
from pathlib import Path
DATA_FILE = Path(__file__).parent / 'data' / 'db.json'
_lock = threading.RLock()

def load_db():
    with _lock:
        if not DATA_FILE.exists(): return {}
        with open(DATA_FILE, encoding='utf-8') as f: return json.load(f)

def save_db(db):
    tmp=DATA_FILE.with_suffix('.tmp')
    with _lock:
        with open(tmp,'w',encoding='utf-8') as f: json.dump(db,f,indent=2)
        os.replace(tmp, DATA_FILE)

def load(name): return load_db().get(name, [])
def save(name, data):
    db=load_db(); db[name]=data; save_db(db)
def next_id(rows): return max((int(r.get('id',0)) for r in rows if isinstance(r,dict)),default=0)+1
