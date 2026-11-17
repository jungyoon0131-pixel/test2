"""쇼핑리스트 데이터 로드/저장 모듈.

app.py는 load_items() / save_items()만 호출한다.
나중에 외부 DB(Supabase, Google Sheets 등)로 바꿀 때 이 파일만 교체하면 된다.

아이템 데이터 모델 (PRD 6.1):
    {
        "id": str,          # uuid4
        "name": str,        # 1~50자
        "checked": bool,    # 구매 완료 여부
        "quantity": int,    # 수량 (기본 1)
        "created_at": str,  # ISO 형식 생성 시각
    }
"""

import json
import os
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "items.json"


def load_items() -> list[dict]:
    """저장된 아이템 목록을 반환한다. 파일이 없거나 깨져 있으면 빈 리스트."""
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []

    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_items(items: list[dict]) -> None:
    """아이템 목록을 JSON 파일로 저장한다. data 폴더가 없으면 만든다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 임시 파일에 먼저 쓰고 교체해서, 저장 도중 실패해도 기존 파일이 깨지지 않게 한다.
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
