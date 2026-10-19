import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from routes.system import bp as system_bp

from config import (FLASK_HOST, FLASK_PORT, FLASK_DEBUG,
                    IZLENEN_EXCEL, DATA_DIR, DEFAULT_MODEL)
from core import database, ollama_client
from core.excel_io import excel_ice_aktar

from routes.candidates import bp as candidates_bp
from routes.excel import bp as excel_bp
from routes.chat import bp as chat_bp
from routes.metrics import bp as metrics_bp
from routes.keep import bp as keep_bp
from routes.word import bp as word_bp

app = Flask(__name__, template_folder="templates", static_folder="static")

app.register_blueprint(system_bp)
app.register_blueprint(candidates_bp)
app.register_blueprint(excel_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(keep_bp)
app.register_blueprint(word_bp)


class ExcelHandler(FileSystemEventHandler):
    def __init__(self):
        self._son = 0

    def _islen(self, event, yol=None):
        if event.is_directory:
            return
        kontrol_yolu = yol or event.src_path
        if Path(kontrol_yolu).name != IZLENEN_EXCEL.name:
            return
        simdi = time.time()
        if simdi - self._son < 2:
            return
        self._son = simdi
        print(f"\n Excel degisti: {kontrol_yolu}")
        ok, msg = excel_ice_aktar(IZLENEN_EXCEL)
        print(f"   -> {msg}")

    def on_modified(self, event):
        self._islen(event)

    def on_created(self, event):
        self._islen(event)

    def on_moved(self, event):
        if hasattr(event, "dest_path") and Path(event.dest_path).name == IZLENEN_EXCEL.name:
            self._islen(event, yol=event.dest_path)


def watcher_baslat():
    DATA_DIR.mkdir(exist_ok=True)
    obs = Observer()
    obs.schedule(ExcelHandler(), str(DATA_DIR), recursive=False)
    obs.daemon = True
    obs.start()
    print(f"Izleniyor: {IZLENEN_EXCEL}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.route("/metrics")
def metrics_page():
    return render_template("metrics.html")


@app.route("/api/ollama/durum")
def ollama_durum():
    return jsonify(ollama_client.durum_ozeti())


@app.route("/api/ollama/warmup", methods=["POST"])
def ollama_warmup():
    from config import PRIMARY_MODELS
    d = request.get_json() or {}
    istenen = (d.get("model") or "").strip()
    # v7 4C-4: bilinmeyen model adi DEFAULT_MODEL'a cevrilir
    m = istenen if istenen in PRIMARY_MODELS else CHAT_MODEL # v17 Final Warmup Fix
    ok = ollama_client.warm_up(m)
    return jsonify({"ok": ok, "model": m})

@app.route("/api/models")
def api_models():
    """UI icin model listesi (tek kaynak: config.PRIMARY_MODELS)."""
    from config import PRIMARY_MODELS
    return jsonify({
        "models": list(PRIMARY_MODELS),
        "default": DEFAULT_MODEL
    })

def _arka_plan():
    print("Ollama warm-up basliyor...")
    # v17 Final Warmup Fix: 14B yerine 7B yukle
    from config import CHAT_MODEL
    ollama_client.warm_up(CHAT_MODEL)

    if IZLENEN_EXCEL.exists():
        print("Mevcut Excel dosyasi bulundu, ice aktariliyor...")
        ok, msg = excel_ice_aktar(IZLENEN_EXCEL)
        print(f"   -> {msg}")

        # Açılış bildirimi için sonucu kaydet
        try:
            import re
            from routes.excel import durum_guncelle
            m = re.search(r"(\d+) yeni aday eklendi, (\d+) zaten mevcuttu", msg)
            if m:
                durum_guncelle(int(m.group(1)), int(m.group(2)), msg)
            else:
                durum_guncelle(0, 0, msg)
        except Exception as e:
            print(f"   (bildirim kaydi hatasi: {e})")


    print("Excel watcher baslatiliyor...")
    watcher_baslat()
    print("Arka plan isleri tamamlandi.")


def _tarayici_ac():
    time.sleep(2)
    try:
        webbrowser.open(f"http://{FLASK_HOST}:{FLASK_PORT}")
        print(f"Tarayici acildi: http://{FLASK_HOST}:{FLASK_PORT}")
    except Exception as e:
        print(f"Tarayici acilamadi: {e}")


if __name__ == "__main__":
    print("Veritabanlari hazirlaniyor...")
    database.init_all()

    threading.Thread(target=_arka_plan, daemon=True).start()
    threading.Thread(target=_tarayici_ac, daemon=True).start()

    print(f"\nFlask basliyor: http://{FLASK_HOST}:{FLASK_PORT}\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)
