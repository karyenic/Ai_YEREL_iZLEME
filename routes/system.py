import os
import subprocess
import threading
import time
from flask import Blueprint, jsonify

bp = Blueprint("system", __name__, url_prefix="/api/system")


@bp.route("/kapat", methods=["POST"])
def kapat():
    try:
        subprocess.run(["taskkill", "/f", "/im", "ollama.exe"],
                       capture_output=True, shell=True)
        subprocess.run(["taskkill", "/f", "/im", "ollama app.exe"],
                       capture_output=True, shell=True)
    except Exception as e:
        print(f"Ollama kapatma hatası: {e}")

    def _exit():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()
    return jsonify({"ok": True})