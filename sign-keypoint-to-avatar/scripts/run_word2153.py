from datetime import datetime
from pathlib import Path
import runpy
import traceback

scripts_dir = Path(__file__).resolve().parent
log_path = scripts_dir / "blender_run.log"

try:
    runpy.run_path(str(scripts_dir / "word2153_retarget_v2.py"), run_name="__main__")
    runpy.run_path(str(scripts_dir / "word2153_face_retarget.py"), run_name="__main__")
    log_path.write_text(
        f"SUCCESS {datetime.now().isoformat()}\n",
        encoding="utf-8",
    )
except Exception:
    log_path.write_text(
        f"FAILED {datetime.now().isoformat()}\n{traceback.format_exc()}",
        encoding="utf-8",
    )
    raise
