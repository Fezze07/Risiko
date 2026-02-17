import io
import os
import sys
from pathlib import Path
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Config
from main import Main


def run_generation_log_check(generations: int = 10, max_workers: int = 1) -> str:
    # Evita qualsiasi watch match interattivo
    Config.DEBUG["WATCH_MATCH"] = False

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        Main(
            generations=generations,
            watch_match=False,
            long_session=False,
            max_workers=max_workers,
        )

    output = buffer.getvalue()
    lines = [line for line in output.splitlines() if line.strip().startswith("GEN ")]
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", "training_gen_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"[manual_training_log_check] Salvato log in {log_path}")
    print(f"[manual_training_log_check] Linee GEN trovate: {len(lines)}")
    for line in lines[-generations:]:
        print(line)
    return log_path


if __name__ == "__main__":
    run_generation_log_check()
