import sqlite3
from flask import Blueprint, jsonify, request
from config import ADAY_DB, OLAY_TIPLERI

from core.database import (
    aday_durum_otomatik_guncelle,
    adaylari_getir,
    aday_ekle,
    aday_sil,
    tum_adaylari_sil,
    aday_karti_getir,
    aday_profil_guncelle,
    aday_gelisme_ekle
)

bp = Blueprint(
    "candidates",
    __name__,
    url_prefix="/api/candidates"
)


@bp.route("", methods=["GET"])
def listele():
    return jsonify(adaylari_getir())


@bp.route("", methods=["POST"])
def ekle():
    d = request.get_json() or {}

    ok = aday_ekle(
        d.get("isim", ""),
        d.get("tarih", ""),
        d.get("aciklama", ""),
        d.get("davet", 0),
        d.get("randevu", 0),
        d.get("plan", 0),
        d.get("kayit", 0),
        d.get("takip", 0),
        d.get("hayir", 0),
        d.get("is_ariyor", 0),
        linkedin_url=d.get("linkedin_url", None),
        durum=d.get("durum", "")
    )

    return jsonify({"ok": ok})

@bp.route("/<int:aday_id>", methods=["GET"])
def kart(aday_id):
    data = aday_karti_getir(aday_id)

    if data is None:
        return jsonify({
            "ok": False,
            "error": "Aday bulunamadı."
        }), 404

    return jsonify({
        "ok": True,
        "data": data
    })


@bp.route("/<int:aday_id>/profil", methods=["PUT"])
def profil_guncelle(aday_id):
    d = request.get_json() or {}

    ok = aday_profil_guncelle(
        aday_id,
        d.get("telefon", ""),
        d.get("email", ""),
        d.get("adres", "")
    )

    if not ok:
        return jsonify({
            "ok": False,
            "error": "Aday profili bulunamadı."
        }), 404

    return jsonify({
        "ok": True,
        "message": "Aday bilgileri güncellendi."
    })


@bp.route("/<int:aday_id>/gelisme", methods=["POST"])
def gelisme_ekle(aday_id):
    d = request.get_json() or {}
    
    tarih = str(d.get("tarih", "")).strip()
    olay_tipi = str(d.get("olay_tipi", "Not")).strip()
    olay_metni = str(d.get("olay_metni", "")).strip()
    durum = str(d.get("durum", "")).strip()
    
    
    # YENI: Randevu tarihi/saati
    randevu_tarihi = str(d.get("randevu_tarihi", "")).strip()
    randevu_saati = str(d.get("randevu_saati", "")).strip()
    
    if not olay_metni and olay_tipi not in ("Sadece Durum Değiştir", "Durum Değişikliği"):
        return jsonify({"ok": False, "error": "Gelisme aciklamasi bos."}), 400
    
    # v11: NET / yumusak hayir ayrimi (metin on kontrol)
    _metin_erken = (olay_metni or "").lower()
    _net_kelimeler = [
        "net hayır", "net hayir",
        "kesinlikle hayır", "kesinlikle hayir",
        "kesin hayır", "kesin hayir",
        "asla", "katiyen", "reddetti",
    ]
    net_hayir = 1 if any(k in _metin_erken for k in _net_kelimeler) else 0

    # Blok çıkarımı: durum "Blok" içeriyorsa VEYA NET hayir denmisse blok=1
    blok_param = 0
    if durum and ("blok" in durum.lower() or "⛔" in durum):
        blok_param = 1
    if net_hayir == 1:
        blok_param = 1

    ok, msg = aday_gelisme_ekle(
        aday_id, tarih, olay_tipi, olay_metni, durum, blok_param
    )
    
    if not ok:
        return jsonify({"ok": False, "error": msg}), 404
    
    # ═══════════════════════════════════════════════════════════
    # OLAY TIPINDEN CHECKBOX CIKARIMI
    # ═══════════════════════════════════════════════════════════
        
    davet = 0
    plan = 0
    kayit = 0
    hayir = 0
    takip = 0
    randevu = 0
    # ═══════════════════════════════════════════════════════════
    # OLAY TIPINDEN CHECKBOX CIKARIMI (config.OLAY_TIPLERI'ndan)
    # ═══════════════════════════════════════════════════════════
    # RANDEVU TARIHI/SAATI DOLUYSA randevu=1
    if randevu_tarihi or randevu_saati:
        randevu = 1
    
    metin = olay_metni.lower()
    
    # OLAY TIPINDEN (birincil) — HTML value ile birebir eslesir
    for _t in OLAY_TIPLERI:
        if _t["html_value"] == olay_tipi:
            _b = _t["bayrak"]
            if _b == "davet":
                davet = 1
            elif _b == "plan":
                plan = 1
            elif _b == "takip":
                takip = 1
            elif _b == "kayit":
                kayit = 1
            elif _b == "hayir":
                hayir = 1
            break
    
    # METINDEN (ikincil - fallback) — kullanicinin serbest metnine gore
    if "plan anlatıldı" in metin or "plan anlatildi" in metin:
        plan = 1
    if "kayıt yapıldı" in metin or "kayit yapildi" in metin or "kayıt oldu" in metin or "kayit oldu" in metin:
        kayit = 1
    if "davet yapıldı" in metin or "davet yapildi" in metin:
        davet = 1
    if "hayır dedi" in metin or "hayir dedi" in metin or "reddetti" in metin:
        hayir = 1
    if "randevu oluştu" in metin or "randevu olustu" in metin:
        randevu = 1    

    
    # ═══════════════════════════════════════════════════════════
    # adaylar tablosunu guncelle
    # ═══════════════════════════════════════════════════════════
    try:
        conn = sqlite3.connect(str(ADAY_DB))
        c = conn.cursor()
        
        updates = []
        params = []
        if davet == 1:
            updates.append("davet = 1")
        if plan == 1:
            updates.append("plan = 1")
        if kayit == 1:
            updates.append("kayit = 1")
        if hayir == 1:
            updates.append("hayir = 1")
        if takip == 1:
            updates.append("takip = 1")
        if randevu == 1:
            updates.append("randevu = 1")
        if randevu_tarihi:
            updates.append("randevu_tarihi = ?")
            params.append(randevu_tarihi)
        if randevu_saati:
            updates.append("randevu_saati = ?")
            params.append(randevu_saati)
        
        if updates:
            sql = f"UPDATE adaylar SET {', '.join(updates)} WHERE id = ?"
            params.append(aday_id)
            c.execute(sql, tuple(params))
            conn.commit()
            print(f"[SYNC] Aday {aday_id} -> {updates}")
        else:
            print(f"[SYNC] Aday {aday_id} -> degisiklik yok")
        
        conn.close()
    except Exception as e:
        print(f"[UYARI] Checkbox sync hatasi: {e}")
    
    # ═══════════════════════════════════════════════════════════
    # OTOMATIK STATU GECISI
    # ═══════════════════════════════════════════════════════════
    try:
        from core.database import aday_durum_otomatik_guncelle
        aday_durum_otomatik_guncelle(
            aday_id,
            davet=davet, plan=plan, kayit=kayit, hayir=hayir,
            net_hayir=net_hayir
        )
    except Exception as e:
        print(f"[UYARI] Otomatik statu hatasi: {e}")
    
    return jsonify({"ok": True, "message": msg})


@bp.route("/<int:aday_id>", methods=["DELETE"])
def sil(aday_id):
    aday_sil(aday_id)
    return jsonify({"ok": True})


@bp.route("/hepsi", methods=["DELETE"])
def hepsini_sil():
    tum_adaylari_sil()
    return jsonify({"ok": True})



@bp.route("/<int:aday_id>/linkedin", methods=["PUT"])
def linkedin_guncelle(aday_id):
    """Adayin LinkedIn URL'sini gunceller."""
    from core.database import aday_linkedin_guncelle
    d = request.get_json() or {}
    linkedin_url = str(d.get("linkedin_url", "")).strip()

    if not linkedin_url:
        return jsonify({"ok": False, "error": "URL bos olamaz."}), 400

    ok = aday_linkedin_guncelle(aday_id, linkedin_url)

    if not ok:
        return jsonify({"ok": False, "error": "Aday bulunamadi."}), 404

    return jsonify({"ok": True, "message": "LinkedIn URL guncellendi."})



@bp.route("/<int:aday_id>/otomatik-durum", methods=["POST"])
def otomatik_durum(aday_id):
    """Checkbox'lara gore statuyu otomatik gunceller."""
    d = request.get_json() or {}
    
    degisti = aday_durum_otomatik_guncelle(
        aday_id,
        davet=int(d.get("davet", 0)),
        plan=int(d.get("plan", 0)),
        kayit=int(d.get("kayit", 0)),
        hayir=int(d.get("hayir", 0))
    )
    
    return jsonify({"ok": True, "degisti": degisti})


@bp.route("/bloklu", methods=["GET"])
def bloklu_listele():
    """Bloklu adaylari listeler (ana listede gizli)."""
    from core.database import bloklu_adaylari_getir
    return jsonify(bloklu_adaylari_getir())


@bp.route("/<int:aday_id>/blok-kaldir", methods=["PUT"])
def blok_kaldir(aday_id):
    """Blok kaydini kaldirir, aday ana listeye doner."""
    from core.database import aday_blok_kaldir
    ok = aday_blok_kaldir(aday_id)
    if not ok:
        return jsonify({"ok": False, "error": "Aday bulunamadi."}), 404
    return jsonify({"ok": True, "message": "Blok kaldirildi."})
