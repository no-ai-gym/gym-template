#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname -- "$SCRIPT_DIR")"
GYM_PYTHON=""
for candidate in "${GYM_PYTHON_BIN:-python3}" python3.14 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,10))' 2>/dev/null; then
    GYM_PYTHON="$candidate"
    break
  fi
done
if [[ -z "$GYM_PYTHON" ]]; then
  echo 'Python 3.10 이상이 필요합니다. 설치 후 다시 실행하세요.' >&2
  exit 1
fi
if [[ ! -x "$ROOT/.gym-venv/bin/python" ]]; then
  "$GYM_PYTHON" -m venv "$ROOT/.gym-venv"
fi
"$ROOT/.gym-venv/bin/python" -m pip install --only-binary=:all: -r "$SCRIPT_DIR/requirements-parser.txt"
exec "$ROOT/.gym-venv/bin/python" "$SCRIPT_DIR/gym.py" setup "$@"
