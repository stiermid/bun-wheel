import sys
import os
from pathlib import Path

def _get_bun_path() -> str:
    bin_dir = Path(__file__).parent / "bin" 
    binary_path = bin_dir / "bun"

    if not binary_path.exists():
        raise FileNotFoundError(f"bun binary not found at {binary_path}")

    return str(binary_path)

def exec_bun() -> None:
    try:
        binary = _get_bun_path()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    args = [binary] + sys.argv[1:]

    os.execv(binary, args)
