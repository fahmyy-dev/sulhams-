import os
import shutil
from datetime import datetime

# Pata njia ya folda kuu ya mradi wako
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(BASE_DIR, 'db.sqlite3')
backup_dir = os.path.join(BASE_DIR, 'backups')

# Kama folda ya backups haipo, itengeneze
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

# Weka jina la backup kulingana na tarehe na saa ya sasa
date_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
backup_path = os.path.join(backup_dir, f'db_backup_{date_str}.sqlite3')

try:
    if os.path.exists(db_path):
        shutil.copyfile(db_path, backup_path)
        print(f"Backup is complete: {backup_path}")
    else:
        print("Faili la database (db.sqlite3) halionekani!")
except Exception as e:
    print(f" backup is incomplete: {e}")