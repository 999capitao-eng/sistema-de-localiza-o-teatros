from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
WEB = ROOT / "web"
DB_PATH = PROCESSED / "radar.sqlite"

USER_AGENT = "RadarDeTeatros/0.1 (contato: seu-email@exemplo.com)"
REQUEST_DELAY = 1.5  # segundos de pausa entre requisicoes ao mesmo servidor

for pasta in (RAW, PROCESSED, MANUAL, WEB):
    pasta.mkdir(parents=True, exist_ok=True)
