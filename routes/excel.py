from flask import Blueprint, jsonify, send_file
import io
from datetime import datetime
from core.excel_io import excel_disa_aktar, excel_ice_aktar
from config import IZLENEN_EXCEL

bp = Blueprint("excel", __name__, url_prefix="/api/excel")


# ═══════════════════════════════════════════════════════════
# Son import sonucunu sakla (açılış bildirimi için)
# ═══════════════════════════════════════════════════════════
_son_import = {
    "zaman": None,
    "eklenen": 0,
    "atlanan": 0,
    "mesaj": "Henüz tarama yapılmadı"
}


def durum_guncelle(eklenen, atlanan, mesaj):
    """_arka_plan() tarafından çağrılır."""
    global _son_import
    _son_import = {
        "zaman": datetime.now().strftime("%H:%M:%S"),
        "eklenen": eklenen,
        "atlanan": atlanan,
        "mesaj": mesaj
    }


@bp.route("/durum", methods=["GET"])
def durum():
    """Frontend açılışta bu endpoint'i çağırır."""
    return jsonify(_son_import)


@bp.route("/import", methods=["POST"])
def import_route():
    """Elle tetiklenen içe aktarma."""
    if not IZLENEN_EXCEL.exists():
        return jsonify({"ok": False, "msg": f"Dosya bulunamadı: {IZLENEN_EXCEL}"}), 404

    ok, msg = excel_ice_aktar(IZLENEN_EXCEL)

    # Sonucu kaydet (bildirim için)
    import re
    m = re.search(r"(\d+) yeni aday eklendi, (\d+) zaten mevcuttu", msg)
    if m:
        durum_guncelle(int(m.group(1)), int(m.group(2)), msg)
    else:
        durum_guncelle(0, 0, msg)

    return jsonify({"ok": ok, "msg": msg})


@bp.route("/export", methods=["GET"])
def export():
    data = excel_disa_aktar()
    if data is None:
        return jsonify({"error": "Veri yok"}), 404
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="linkedin_adaylar.xlsx"
    )
