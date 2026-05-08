#!/usr/bin/env python3
"""Write the FastAPI OpenAPI schema to stdout as JSON (CI artifact)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Docker / local: app package lives on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402


def main() -> None:
    app = create_app()
    print(json.dumps(app.openapi(), indent=2))


if __name__ == "__main__":
    main()
