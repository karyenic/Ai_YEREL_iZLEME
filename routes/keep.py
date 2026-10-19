"""Keep'ten aday aktarma - Gelismis parser."""
from flask import Blueprint, jsonify, request
from datetime import datetime
import re
import hashlib
import unicodedata
from core.database import aday_ekle, adaylari_getir

bp = Blueprint("keep", __name__, url_prefix="/api/keep")


# ═══════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════
def _normalize(s):
    """Turkce karakter + bosluk normalize."""
    if not s:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    for ch in ["\u00a0", "\u200b", "\u200c", "\u200d", "\ufeff"]:
        s = s.replace(ch, " ")
    return " ".join(s.split()).strip().lower()


def _isim_url_cikar(url):
    """linkedin.com/in/cem-denizer-07906435 -> Cem Denizer"""
    if not url:
        return ""
    match = re.search(r'linkedin\.com/in/([^/?&#]+)', url, re.IGNORECASE)
    if not match:
        return ""
    slug = match.group(1)
    # Tireyi bosluga cevir
    slug = slug.replace("-", " ")
    # URL decode
    try:
        from urllib.parse import unquote
        slug = unquote(slug)
    except Exception:
        pass
    # Kelimelere ayir
    kelimeler = slug.split()
    # Rakamli ve 5+ karakterli kelimeleri temizle (07906435 gibi)
    kelimeler = [k for k in kelimeler if not (len(k) >= 5 and any(c.isdigit() for c in k))]
    # Sadece rakam olan kelimeleri temizle
    kelimeler = [k for k in kelimeler if not k.isdigit()]
    if not kelimeler:
        return ""
    # Ilk harfleri buyut
    return " ".join(k.capitalize() for k in kelimeler)


def _url_bul(metin):
    """Metinde LinkedIn URL ara."""
    if not metin:
        return None
    match = re.search(
        r'https?://[^\s)]*linkedin\.com/in/[^\s)]+',
        metin,
        re.IGNORECASE
    )
    return match.group(0) if match else None


def _uniq_hash(isim, linkedin_url):
    """Uniq hash: URL varsa URL, yoksa isim."""
    if linkedin_url:
        key = _normalize(linkedin_url)
    else:
        key = _normalize(isim)
    if not key:
        return None
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _keep_parse(metin):
    """
    Keep notunu ayristirir.
    
    Formatlar:
      1) • 🟡 Isim: Aciklama
      2) • 🟢 Isim.
      3) • 🟡 Isim
      4) • 🟡 https://linkedin.com/in/...
      5) • 🟢 Isim: Aciklama — URL
    """
    adaylar = []
    atlanan = 0

    for satir in metin.split("\n"):
        satir = satir.strip()
        if not satir or not satir.startswith("•"):
            atlanan += 1
            continue

        # • isaretini kaldir
        satir = satir.lstrip("•").strip()

        # Durum emoji tespit
        durum = "belirsiz"
        durum_etiketi = "Yeni"
        for emoji, d, etiket in [
            ("🟢", "yesil", "🟢 Aktif"),
            ("🟡", "sari", "🟡 Bekliyor"),
            ("🔴", "kirmizi", "🔴 Olumsuz"),
            ("🔥", "sicak", "🔥 Sıcak"),
            ("🟠", "turuncu", "🟡 Bekliyor"),
        ]:
            if emoji in satir:
                durum = d
                durum_etiketi = etiket
                satir = satir.replace(emoji, "").strip()
                break

        # URL ara
        linkedin_url = _url_bul(satir)

        # URL'yi satirdan cikar
        if linkedin_url:
            satir = satir.replace(linkedin_url, "").strip()

        # Isim + Aciklama ayir
        if ":" in satir:
            parcalar = satir.split(":", 1)
            isim = parcalar[0].strip()
            aciklama = parcalar[1].strip() if len(parcalar) > 1 else ""
        else:
            isim = satir.strip().rstrip(".")
            aciklama = ""

        # Isim yoksa URL'den cikar
        if not isim and linkedin_url:
            isim = _isim_url_cikar(linkedin_url)

        # Isim hala yoksa atla
        if not isim:
            atlanan += 1
            continue

        # Fazla bosluk / tire temizle
        isim = re.sub(r"\s+", " ", isim).strip(" .-–—")

        adaylar.append({
            "isim": isim,
            "aciklama": aciklama[:500],
            "durum": durum_etiketi,
            "linkedin_url": linkedin_url,
            "uniq_hash": _uniq_hash(isim, linkedin_url)
        })

    return adaylar, atlanan


# ═══════════════════════════════════════════════════════════
# ENDPOINT'LER
# ═══════════════════════════════════════════════════════════
@bp.route("/parse", methods=["POST"])
def parse():
    """Keep metnini parse eder (DB'ye eklemez), onizleme doner."""
    d = request.get_json() or {}
    metin = d.get("metin", "").strip()

    if not metin:
        return jsonify({"ok": False, "error": "Metin bos"}), 400

    adaylar, atlanan = _keep_parse(metin)

    yesil = sum(1 for a in adaylar if "Aktif" in a["durum"])
    sari = sum(1 for a in adaylar if "Bekliyor" in a["durum"])
    urlu = sum(1 for a in adaylar if a["linkedin_url"])

    return jsonify({
        "ok": True,
        "adaylar": adaylar,
        "toplam": len(adaylar),
        "yesil": yesil,
        "sari": sari,
        "urlu": urlu,
        "atlanan": atlanan
    })


@bp.route("/import", methods=["POST"])
def import_route():
    """Keep metnini parse eder ve DB'ye ekler."""
    d = request.get_json() or {}
    metin = d.get("metin", "").strip()

    if not metin:
        return jsonify({"ok": False, "error": "Metin bos"}), 400

    adaylar, atlanan = _keep_parse(metin)

    if not adaylar:
        return jsonify({
            "ok": False,
            "error": "Hic aday bulunamadi. Format: • [🟢/🟡] Isim: Aciklama"
        }), 400

    bugun = datetime.now().strftime("%d %m %y")
    eklenen = 0
    atlanan_db = 0

    for a in adaylar:
        aciklama = a["aciklama"]
        h = a["uniq_hash"]

        ok = aday_ekle(
            a["isim"],
            bugun,
            aciklama,
            0, 0, 0, 0, 0, 0,
            1,
            kaynak_hash=h,
            linkedin_url=a["linkedin_url"]
        )
        if ok:
            eklenen += 1
        else:
            atlanan_db += 1

    return jsonify({
        "ok": True,
        "eklenen": eklenen,
        "atlanan": atlanan_db,
        "format_atlanan": atlanan,
        "mesaj": f"{eklenen} yeni aday eklendi, {atlanan_db} zaten mevcuttu"
    })
