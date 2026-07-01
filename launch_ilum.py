# -*- coding: utf-8 -*-
"""Distribution launcher for ILUM.

This small wrapper runs before importing the heavy application modules, so
missing dependencies and first-run errors are written to a visible log instead
of disappearing behind pythonw.exe.
"""
from __future__ import annotations

import ctypes
import os
import sys
import traceback
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ERROR_LOG = BASE_DIR / "ilum_startup_error.log"


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "ILUM AI - Error de inicio", 0x10)
    except Exception:
        pass


def main() -> int:
    os.chdir(BASE_DIR)

    try:
        import main as ilum_main

        ilum_main.main()
        return 0
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 0
    except Exception:
        details = traceback.format_exc()
        ERROR_LOG.write_text(details, encoding="utf-8")
        _show_error(
            "ILUM no pudo iniciar.\n\n"
            "Revisa el archivo ilum_startup_error.log en la carpeta del programa.\n\n"
            "Si acabas de descargar el repo, ejecuta Instalar_ILUM.bat y espera a que termine."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
