"""WebUI Next 统一路径常量。"""

from pathlib import Path

# utils/webui_next/paths.py -> 项目根目录
BASE_DIR = Path(__file__).resolve().parents[2]

CONFIG_FILE = BASE_DIR / "config" / "bot.yaml"
BACKUP_DIR = BASE_DIR / "config" / "backups"
BLACKLIST_FILE = BASE_DIR / "data" / "blacklist.json"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
