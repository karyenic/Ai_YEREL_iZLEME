# -*- coding: utf-8 -*-
"""
core/ai_postprocess.py
AI JSON cikitisini temizler ve zenginlestirir.

- bey_hanim_duzelt: cinsiyet tahmini ile "Bey/Hanim" yerine "Bey" veya "Hanım"
- isim_normalize: TR karakter eslestirme (Gökalp = Gokalp)
- skor_kategoriden: durum -> sabit skor
- mesaj_temizle: kisisel_not kopyasini mesajdan cikar
"""
import re
from typing import Optional

# --- Cinsiyet tahmini icin yaygin TR isimleri ---
KADIN_ISIMLER = {
    "ayşe", "fatma", "emine", "hatice", "zeynep", "elif", "merve", "ezgi",
    "nilay", "begüm", "ilke", "yağmur", "gamze", "burcu", "pınar", "selin",
    "ayça", "aylin", "özge", "gizem", "ceren", "ece", "defne", "melis",
    "yağmur", "nehir", "inci", "aslı", "yasemin", "gül", "gülsüm", "dilek",
    "derya", "cansu", "belgin", "ayşegül", "şeyda", "sevgi", "nur", "nisa",
    "mine", "mihriban", "lale", "kübra", "jale", "ipek", "hande", "fulya",
    "fulden", "ezgi", "esra", "esin", "erdem", "duygu", "damla", "çağla",
    "berna", "beliz", "aycan", "aybike", "asuman", "arzu", "bahar",
}

ERKEK_ISIMLER = {
    "ahmet", "mehmet", "mustafa", "ali", "hüseyin", "hasan", "ibrahim",
    "osman", "yusuf", "murat", "ömer", "ramazan", "halil", "ismail",
    "süleyman", "kemal", "engin", "olgun", "berat", "tolga", "serkan",
    "uğur", "uğurcan", "umut", "furkan", "fatih", "erdem", "emre",
    "erol", "erdi", "engin", "emrah", "edip", "dursun", "doğukan",
    "cem", "can", "caner", "birol", "berk", "berkay", "barış", "burak",
    "bora", "bilal", "bekir", "batu", "batuhan", "barbaros", "aykut",
    "atilla", "atilla", "aslıhan", "arif", "alper", "alperen", "alp",
    "ali", "alican", "akın", "adnan", "abdullah", "abdurrahman",
    "serhat", "sinan", "taner", "tarık", "tolunay", "turgay",
    "yakup", "yavuz", "yiğit", "zafer", "zeki", "volkan", "vedat",
    "yağız", "yahya", "yasin", "yılmaz", "yusuf", "zekeriya",
}

def cinsiyet_tahmin(isim: str) -> Optional[str]:
    """Isimden cinsiyet tahmini. 'k' = kadin, 'e' = erkek, None = bilinmiyor."""
    if not isim:
        return None
    ilk = isim.strip().split()[0].lower()
    # TR karakter normalizasyonu
    ilk = (ilk
           .replace("ı", "i").replace("İ", "i").replace("i̇", "i")
           .replace("ğ", "g").replace("ü", "u").replace("ş", "s")
           .replace("ö", "o").replace("ç", "c"))
    # Hem orijinal hem normalize edilmis halde ara
    if ilk in KADIN_ISIMLER:
        return "k"
    if ilk in ERKEK_ISIMLER:
        return "e"
    # Normalize edilmis listede de ara
    for kadin in KADIN_ISIMLER:
        if _tr_norm(kadin) == ilk:
            return "k"
    for erkek in ERKEK_ISIMLER:
        if _tr_norm(erkek) == ilk:
            return "e"
    return None

def _tr_norm(s: str) -> str:
    """TR karakter normalizasyonu (karsilastirma icin)."""
    if not s:
        return ""
    return (s.lower()
            .replace("ı", "i").replace("i̇", "i")
            .replace("ğ", "g").replace("ü", "u").replace("ş", "s")
            .replace("ö", "o").replace("ç", "c")
            .strip())

def bey_hanim_duzelt(mesaj: str, isim: str) -> str:
    """'Bey/Hanim' yerine cinsiyete uygun hitap."""
    if not mesaj:
        return mesaj

    c = cinsiyet_tahmin(isim)

    # "Bey/Hanim" veya "Bey/Hanım" hepsini yakala
    if c == "k":
        mesaj = re.sub(r"\bBey\s*/\s*Han[ıi]m\b", "Hanım", mesaj)
        mesaj = re.sub(r"\bBey\b(?!\s*/)", "Hanım", mesaj)  # tek basina Bey -> Hanim (nadiren yanlis olabilir)
    elif c == "e":
        mesaj = re.sub(r"\bBey\s*/\s*Han[ıi]m\b", "Bey", mesaj)
        mesaj = re.sub(r"\bHan[ıi]m\b(?!\s*/)", "Bey", mesaj)
    else:
        # Cinsiyet bilinmiyor -> "Bey/Hanım" yerine notr form
        mesaj = re.sub(r"\bBey\s*/\s*Han[ıi]m\b", "(Bey/Hanım)", mesaj)

    # Kalan Bey/Hanim varsa temizle
    mesaj = re.sub(r"\bBey\s*/\s*Han[ıi]m\b", "", mesaj)
    mesaj = re.sub(r"\s+", " ", mesaj).strip()

    return mesaj

def mesaj_temizle(mesaj: str, kisisel_not: str = "") -> str:
    """kisisel_not kopyasini mesajdan cikar, dogal hale getir."""
    if not mesaj:
        return mesaj

    mesaj = mesaj.strip()

    # "Merhaba X Bey/Hanim, <kisisel_not>. " gibi kaliplari temizle
    # Basit yaklasim: mesajdaki fazlalik ifadeleri kes
    if kisisel_not:
        kn = kisisel_not.strip().rstrip(".")
        # kisisel_not'u mesajdan cikar (kucuk-buyuk harf duyarsiz)
        if kn and len(kn) > 10:
            mesaj = re.sub(re.escape(kn) + r"\.?\s*", "", mesaj, flags=re.IGNORECASE)

    # "Merhaba X, " sonrasi dogal olmali
    mesaj = re.sub(r"^Merhaba\s+[^,]+,?\s*", "Merhaba, ", mesaj)
    mesaj = re.sub(r"\s+", " ", mesaj).strip()

    return mesaj

# Durum -> skor eslemesi
DURUM_SKOR = {
    "hic_temas_yok": 30,
    "kaba_listede": 45,
    "davet_edildi": 55,
    "randevu_var": 65,
    "plan_yapildi": 75,
    "randevu_iptal": 50,
    "takip": 60,
    "sicak": 85,
    "olumsuz": 20,
}

def skor_kategoriden(durum: str, mevcut_skor: Optional[int] = None) -> int:
    """Duruma gore sabit skor. Model skoru dikkate alinmaz."""
    return DURUM_SKOR.get((durum or "").strip(), 50)

def isim_normalize(isim: str) -> str:
    """Karsilastirma icin TR normalize."""
    return _tr_norm(isim)

def isim_eslesme(ai_isim: str, db_isimler: list) -> Optional[str]:
    """AI'nin dondurdugu ismi DB'deki gercek isimle eslestir.
    Returns: DB'deki isim veya None."""
    if not ai_isim:
        return None
    a_norm = isim_normalize(ai_isim)
    for db_isim in db_isimler:
        if isim_normalize(db_isim) == a_norm:
            return db_isim
    return None



def _haftalik_plan_otomatik(adaylar):
    """Adaylardan otomatik 7 gunluk plan olustur."""
    if not adaylar:
        return []
    GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    DURUM_EYLEM = {
        "randevu_iptal": "Yeniden randevu talebi gonder",
        "plan_yapildi": "Geri bildirim iste",
        "randevu_var": "Randevu oncesi hatirlatma",
        "takip": "Takip mesaji gonder",
        "sicak": "Detayli bilgi paylas",
        "davet_edildi": "Davet yanitini bekle",
        "kaba_listede": "Tanisma mesaji gonder",
        "hic_temas_yok": "Ilk temas kur",
        "olumsuz": "Dokunma",
    }
    plan = []
    for i, gun in enumerate(GUNLER):
        if i < len(adaylar):
            a = adaylar[i]
            plan.append({
                "gun": gun,
                "aday": a.get("isim", ""),
                "eylem": DURUM_EYLEM.get(a.get("durum", ""), "Mesaj gonder"),
            })
        else:
            plan.append({"gun": gun, "aday": "", "eylem": ""})
    return plan


def postprocess(ai_json: dict, db_isimler: list, huni: dict) -> dict:
    """Ana post-process fonksiyonu.
    
    Args:
        ai_json: modelin dondurdugu ham JSON
        db_isimler: DB'deki gecerli aday isimleri listesi
        huni: _huni_hesapla ciktisi
    
    Returns:
        temizlenmis + zenginlestirilmis JSON
    """
    GECERLI_DURUMLAR = set(DURUM_SKOR.keys())
    GECERLI_DARBOGAZ = {"davet", "randevu", "plan", "kayit", "yok"}

    temiz = {}

    # 1) Huni darbogaz
    darbogaz = ai_json.get("huni_darbogaz", "yok")
    if darbogaz not in GECERLI_DARBOGAZ:
        darbogaz = "yok"
    temiz["huni_darbogaz"] = darbogaz

    # 2) Huni yorumu (template + model ozel)
    darbogaz_metin = {
        "davet": f"Kaba listeden davete gecis darbogaz (%{huni.get('oran_kabadan_davete', 0)})",
        "randevu": f"Davetten randevuya gecis darbogaz (%{huni.get('oran_davetten_randevuya', 0)})",
        "plan": f"Randevudan plan sunumuna gecis darbogaz (%{huni.get('oran_randevudan_plana', 0)})",
        "kayit": f"Plandan kayda gecis darbogaz (%{huni.get('oran_plandan_kayda', 0)})",
        "yok": "Belirgin darbogaz yok",
    }
    ozel = (ai_json.get("huni_yorumu_ozel") or "").strip()
    if ozel and len(ozel) > 200:
        ozel = ozel[:200] + "..."
    temiz["huni_yorumu"] = f"{darbogaz_metin[darbogaz]}. {ozel}".strip()

    # 3) Adaylar - dedupe + isim eslestir
    gorulen = set()
    temiz_adaylar = []
    ADAY_ALANLARI = {"isim", "durum", "kisisel_not", "sonraki_adim", "mesaj_metni"}

    for a in ai_json.get("adaylar", []):
        ai_isim = (a.get("isim") or "").strip()
        if not ai_isim:
            continue

        # DB'deki gercek isimle eslestir
        db_isim = isim_eslesme(ai_isim, db_isimler)
        if not db_isim:
            # Eslestirilemedi, atla
            continue

        key = isim_normalize(db_isim)
        if key in gorulen:
            continue
        gorulen.add(key)

        # Durum
        durum = (a.get("durum") or "kaba_listede").strip()
        if durum not in GECERLI_DURUMLAR:
            durum = "kaba_listede"

        # Mesaj temizle + cinsiyet
        kisisel = (a.get("kisisel_not") or "").strip()
        mesaj = (a.get("mesaj_metni") or "").strip()
        mesaj = mesaj_temizle(mesaj, kisisel)
        mesaj = bey_hanim_duzelt(mesaj, db_isim)

        # Cok uzun mesajlari kisalt
        if len(mesaj) > 400:
            mesaj = mesaj[:400] + "..."

        yeni = {
            "isim": db_isim,
            "durum": durum,
            "skor": skor_kategoriden(durum, a.get("skor")),
            "kisisel_not": kisisel[:200],
            "sonraki_adim": (a.get("sonraki_adim") or "").strip()[:200],
            "mesaj_metni": mesaj,
        }
        temiz_adaylar.append(yeni)

    # Oncelik sirasi: durum bazli
    DURUM_ONCELIK = {
        "randevu_iptal": 0, "plan_yapildi": 1, "randevu_var": 2,
        "takip": 3, "sicak": 4, "davet_edildi": 5,
        "kaba_listede": 6, "hic_temas_yok": 7, "olumsuz": 8,
    }
    temiz_adaylar.sort(key=lambda x: (DURUM_ONCELIK.get(x["durum"], 99), -x["skor"]))
    temiz["adaylar"] = temiz_adaylar[:10]

    # 4) Haftalik plan
    GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    plan = ai_json.get("haftalik_plan") or _haftalik_plan_otomatik(temiz.get("adaylar", []))
    temiz_plan = []
    for i, p in enumerate(plan[:7]):
        if isinstance(p, dict):
            aday = (p.get("aday") or "").strip()
            # Isim eslestir
            if aday:
                db_isim = isim_eslesme(aday, db_isimler)
                aday = db_isim or ""
            temiz_plan.append({
                "gun": GUNLER[i] if i < len(GUNLER) else p.get("gun", ""),
                "aday": aday,
                "eylem": (p.get("eylem") or "").strip()[:150],
            })
    temiz["haftalik_plan"] = temiz_plan

    return temiz


# --- Bagimsiz test ---
if __name__ == "__main__":
    import json
    # Ornek: Test 7 cikitisini post-process'ten gecir
    ai_json = {
        "huni_darbogaz": "plan",
        "huni_yorumu_ozel": "Toplam 117 aday, 2 davet, 2 randevu.",
        "adaylar": [
            {
                "isim": "Berat Çınar",
                "durum": "plan_yapildi",
                "skor": 70,
                "kisisel_not": "Mesajıma yanıt vererek ilgi gösterdi.",
                "sonraki_adim": "3 gun sonra geri bildirim iste",
                "mesaj_metni": "Merhaba Berat Bey/Hanim, Mesajıma yanıt vererek ilgi gösterdi. Plan sunumumuzu incelediniz mi?",
            },
            {
                "isim": "Ezgi tekin",
                "durum": "kaba_listede",
                "skor": 45,
                "kisisel_not": "Linkedin bağlantısını kabul etti.",
                "sonraki_adim": "Davet mesaji gonder",
                "mesaj_metni": "Merhaba Ezgi Bey/Hanim, Linkedin bağlantısını kabul etti. Kisa bir gorusme yapabilir miyiz?",
            },
            {
                "isim": "Yesim Gökalp",  # DB'de "Yesim Gokalp" olabilir
                "durum": "kaba_listede",
                "skor": 45,
                "kisisel_not": "Yeni firsatlara acik",
                "sonraki_adim": "Davet mesaji gonder",
                "mesaj_metni": "Merhaba Yesim Bey/Hanim, ...",
            },
        ],
        "haftalik_plan": [
            {"gun": "Pazartesi", "aday": "Berat Çınar", "eylem": "Geri bildirim iste"},
        ],
    }
    db_isimler = ["Berat Çınar", "Ezgi tekin", "Yesim Gokalp", "Ahmet Mutluhan"]
    huni = {
        "toplam": 117, "davet": 2, "randevu": 2, "plan": 2, "kayit": 0,
        "oran_kabadan_davete": 1.7, "oran_davetten_randevuya": 100.0,
        "oran_randevudan_plana": 100.0, "oran_plandan_kayda": 0.0,
    }
    sonuc = postprocess(ai_json, db_isimler, huni)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))