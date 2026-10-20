from flask import Blueprint, Response, request, jsonify
import pandas as pd
from datetime import datetime
from core.database import adaylari_getir, tarih_parse
from core.ollama_client import chat_stream
from config import DEFAULT_MODEL, DEFAULT_FALLBACK, CHAT_MODEL  # v17 Metrics 7B Patch

bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def _huni_hesapla(adaylar):
    """Kaba listeden kayda kadar GERÇEK huni (bir onceki adima gore %).
    Bu rakamlar LLM'e DOGRU VERI olarak verilir - LLM kendi hesaplamaz,
    hesaplanmis rakami yorumlar (halusinasyonu engeller).

    v14: Bloklu adaylar huniden HARIC tutulur (net hayir).
    Cagiran taraf adaylari_getir(bloklular_dahil=True) kullanmali.
    """
    # v14: Bloklu adaylari ayir
    bloklu_sayisi = sum(1 for a in adaylar if int(a.get('blok') or 0))
    adaylar = [a for a in adaylar if not int(a.get('blok') or 0)]

    toplam = len(adaylar)

    def s(k):
        return sum(int(a.get(k) or 0) for a in adaylar)

    def s_kumulatif(*anahtarlar):
        """Aday bu anahtarlardan EN AZ BIRINE sahipse 1 sayar.
        Huni mantigi: bir sonraki adima gecen, onceki adimlari da gecmis sayilir.
        Yapiskan flag sorununu cozer (1 davet + 3 randevu -> %300 bug'i).
        """
        return sum(
            1 for a in adaylar
            if any(int(a.get(k) or 0) for k in anahtarlar)
        )

    # Ham sayimlar (huni disi metrikler icin)
    takip, hayir = s('takip'), s('hayir')
    is_ariyor = s('is_ariyor')

    # Kumulatif huni sayimlari
    davet   = s_kumulatif('davet', 'randevu', 'plan', 'kayit')
    randevu = s_kumulatif('randevu', 'plan', 'kayit')
    plan    = s_kumulatif('plan', 'kayit')
    kayit   = s_kumulatif('kayit')

    def oran(pay, payda):
        return round(pay / payda * 100, 1) if payda else 0.0

    # Hala surecte olan (ne kayit oldu ne red aldi)
    aktif_takipte = sum(
        1 for a in adaylar
        if not int(a.get('kayit') or 0) and not int(a.get('hayir') or 0)
    )

    return {
        "toplam": toplam,
        "davet": davet, "randevu": randevu, "plan": plan,
        "kayit": kayit, "takip": takip, "hayir": hayir,
        "is_ariyor": is_ariyor,
        "aktif_takipte": aktif_takipte,
        "bloklu": bloklu_sayisi,
        # Zincirdeki her adimin BIR ONCEKI adima gore donusum orani
        "oran_kabadan_davete": oran(davet, toplam),
        "oran_davetten_randevuya": oran(randevu, davet),
        "oran_randevudan_plana": oran(plan, randevu),
        "oran_plandan_kayda": oran(kayit, plan),
        # Ucdan uca: kaba listeden kayda genel basari orani
        "oran_uctan_uca": oran(kayit, toplam),
        # v14: Red orani = yumusak hayir + net (blok) / genel toplam
        "oran_red": oran(hayir + bloklu_sayisi, toplam + bloklu_sayisi),
        # Eskiye uyumluluk
        "davet_randevu_oran": oran(randevu, davet),
        "plan_kayit_oran": oran(kayit, plan),
    }


def tr_norm(s):
    """Turkce uyumlu lowercase. I/İ -> i, I -> i, diger Turkce -> ASCII.
    translate + lower kombinasyonu; birlesik noktali i sorununu onler.
    """
    if not s:
        return ""
    tr = str.maketrans(
        "çğıöşüÇĞİÖŞÜ",
        "cgiosuCGIOSU"
    )
    return str(s).translate(tr).lower()


def _riskli_adaylar(adaylar, limit=10):
    """Her aktif aday icin: gercek temas ayrimi + son 5 olay.
    Excel Geçmişi ve Aday Kaydı = VERI GIRISI, temas DEGIL."""
    from core.database import aday_karti_getir

    # Bu olay tipleri temas SAYILMAZ (otomatik/veri girisi)
    TEMAS_DISI = ("Excel Geçmişi", "Excel Gecmisi", "Aday Kaydı", "Aday Kaydi")

    aktif = [
        a for a in adaylar
        if not int(a.get('kayit') or 0) and not int(a.get('hayir') or 0)
    ]

    bugun = pd.Timestamp.now().normalize()
    sonuc = []

    for a in aktif:
        kart = aday_karti_getir(a.get("id"))
        if not kart:
            continue
        gecmis = kart.get("gecmis", []) or []
        if not gecmis:
            continue

        # Tum gecmis tarihleri
        tum_tarihler = []
        gercek_temas_tarihleri = []
        for o in gecmis:
            t = tarih_parse(o.get("tarih"))
            if pd.isna(t):
                continue
            tum_tarihler.append(t)
            tip = (o.get("olay_tipi") or "").strip()
            if tip not in TEMAS_DISI:
                gercek_temas_tarihleri.append(t)

        if not tum_tarihler:
            continue

        # Sisteme kayit tarihi = ilk olay
        ilk_t = min(tum_tarihler)
        # Gercek temas = Excel/Aday Kaydi HARIC son olay
        if gercek_temas_tarihleri:
            son_gercek_t = max(gercek_temas_tarihleri)
            gercek_temas_var = True
            gun_temassiz = int((bugun - son_gercek_t.normalize()).days)
            son_temas_str = son_gercek_t.strftime("%d.%m.%Y")
        else:
            son_gercek_t = None
            gercek_temas_var = False
            # Hic temas yoksa, sisteme kayittan beri gecen sure
            gun_temassiz = int((bugun - ilk_t.normalize()).days)
            son_temas_str = "-"

        # Asama (net etiketler)
        if not gercek_temas_var:
            asama = "hic_temas_yok"
        elif a.get('plan'):
            asama = "plan_yapildi"
        elif a.get('randevu'):
            asama = "randevu_var"
        elif a.get('davet'):
            asama = "davet_edildi"
        else:
            asama = "kaba_listede"

        # Son 5 olay
        olaylar = []
        for o in gecmis[:5]:
            metin = (o.get("olay_metni") or "").strip()
            if len(metin) > 400:
                metin = metin[:400] + "..."
            olaylar.append({
                "tarih": o.get("tarih", ""),
                "tip": o.get("olay_tipi", ""),
                "metin": metin,
            })

        sonuc.append({
            "isim": a.get("isim", "?"),
            "durum": kart.get("durum", "?"),
            "telefon": (kart.get("telefon") or "").strip(),
            "email": (kart.get("email") or "").strip(),
            "gercek_temas_var": gercek_temas_var,
            "gun_temassiz": gun_temassiz,
            "asama": asama,
            "sisteme_kayit": ilk_t.strftime("%d.%m.%Y"),
            "son_gercek_temas": son_temas_str,
            "olaylar": olaylar,
            "_sort": -gun_temassiz,
        })

    ASAMA_ONCELIK = {"plan_yapildi": 0, "randevu_var": 1, "davet_edildi": 2, "kaba_listede": 3, "hic_temas_yok": 4}
    sonuc.sort(key=lambda x: (ASAMA_ONCELIK.get(x["asama"], 99), x["_sort"]))
    return sonuc[:limit]

def _firsat_adaylar(adaylar, limit=10):
    """Son 7 gundeki olumlu sinyalleri tarar, firsat adaylarini dondurur."""
    import re
    from core.database import aday_karti_getir

    def _norm(s):
        if not s:
            return ""
        tr = str.maketrans(
            "\u00e7\u011f\u0131\u00f6\u015f\u00fc\u00c7\u011e\u0130\u00d6\u015e\u00dc",
            "cgiosuCGIOSU"
        )
        return s.translate(tr).lower()

    # v15: cumlecik bolucu + engel kelimeler (yanlis pozitifleri engeller)
    _CUM_SPLIT_RE = re.compile(
        r"[,;!?]|\.\s+|\b(?:ama|fakat|ancak|lakin|oysa|halbuki)\b", re.I
    )
    _ENGEL_KELIMELER = ("yok", "henuz", "vermedi", "bulamadim",
                        "istedim", "gonderdim", "gonderilecek",
                        "aranacak", "alindi", "etmedi", "kabul etmedi",
                        "planliyor", "planlanacak", "anlattim", "bahsettim",
                        "sundum", "teklif ettim")

    def _cumleciklere_bol(s):
        parts = _CUM_SPLIT_RE.split(s or "")
        return [p.strip() for p in parts if p.strip()]

    def _cumlecik_engelli(c):
        return any(e in c for e in _ENGEL_KELIMELER)

    # (kod, agirlik, etiket, anahtar_kelimeler) - kelime tabanli
    SINYALLER = [
        ("bilgi_istedi",     7, "Bilgi/detay istedi",
         ["bilgi istedi", "detay istedi", "detaylari ned",
          "daha fazla bilgi", "bilgi almak istiyor"]),
        ("davet_kabul",      6, "LinkedIn davetini kabul etti",
         ["davetimi kabul", "daveti kabul",
          "baglanti istegimi kabul", "baglanti davetimi kabul"]),
        ("is_birligi_ilgi",  7, "Is birligine ilgi gosterdi",
         ["is birligine ilgi",
          "is birligi ile ilgili", "ilgi duyuyor",
          "ilgi gosterdi", "degerlendirecegini"]),
        ("olumlu_yanit",     5, "Olumlu yanit / tesekkur",
         ["tesekkur ederim", "memnuniyet",
          "memnun oldum", "nazik mesaj"]),
    ]

    # (kod, agirlik, etiket, regex) - kalip tabanli, kelime sinirli
    SINYAL_PATTERNS = [
        ("baglanti_istegi", 10, "Kendi baglanti istegi gonderdi",
         re.compile(r"\bbaglanti isteg\w*.*\bgonderdi\b", re.I)),
        ("telefon_verdi",   12, "Telefon numarasi verdi",
         re.compile(r"\b(telefon|numara)\w*\s+(numaras\w*\s+)?(verdi|paylasti|iletti|birakti)\b", re.I)),
        ("mesaj_gonderdi",   4, "Iki yonlu mesaj",
         re.compile(r"\b(mesaj|yanit)\w*.*\bgonderdi\b", re.I)),
    ]

    aktif = [
        a for a in adaylar
        if not int(a.get('kayit') or 0) and not int(a.get('hayir') or 0)
    ]

    bugun = pd.Timestamp.now().normalize()
    PENCERE = 7

    sonuc = []

    for a in aktif:
        kart = aday_karti_getir(a.get("id"))
        if not kart:
            continue
        gecmis = kart.get("gecmis", []) or []
        if not gecmis:
            continue

        bulunan_sinyaller = []
        toplam_agirlik = 0

        for o in gecmis:
            t = tarih_parse(o.get("tarih"))
            if pd.isna(t):
                continue
            gun_fark = int((bugun - t.normalize()).days)
            if gun_fark > PENCERE or gun_fark < 0:
                continue

            metin = (o.get("olay_metni") or "")
            metin_norm = _norm(metin)

            cumlecikler = [
                c for c in _cumleciklere_bol(metin_norm)
                if not _cumlecik_engelli(c)
            ]
            if not cumlecikler:
                continue

            def _sinyal_ekle(kod, etiket, agirlik):
                bulunan_sinyaller.append({
                    "kod": kod,
                    "etiket": etiket,
                    "agirlik": agirlik,
                    "tarih": o.get("tarih", ""),
                    "metin": metin[:150],
                })

            for kod, agirlik, etiket, kelimeler in SINYALLER:
                if any(s["kod"] == kod for s in bulunan_sinyaller):
                    continue
                for c in cumlecikler:
                    if any(k in c for k in kelimeler):
                        _sinyal_ekle(kod, etiket, agirlik)
                        toplam_agirlik += agirlik
                        break

            for kod, agirlik, etiket, pat in SINYAL_PATTERNS:
                if any(s["kod"] == kod for s in bulunan_sinyaller):
                    continue
                for c in cumlecikler:
                    if pat.search(c):
                        _sinyal_ekle(kod, etiket, agirlik)
                        toplam_agirlik += agirlik
                        break

        # Olumsuz sinyal kontrolu - son 7 gunde olumsuz kelime varsa firsat degil
        OLUMSUZ_KELIMELER = ("ilgilenmedi", "olumsuz", "reddetti",
                              "istemiyor", "hayir dedi", "uyumsuz",
                              "net hayir", "kesinlikle hayir",
                              "yanit vermedi", "donmedi")
        # "asla" icin kelime siniri - "Aslan" adli aday yakalanmasin
        _ASLA_RE = re.compile(r"\basla\b", re.I)
        olumsuz_var = False
        for o in gecmis:
            t = tarih_parse(o.get("tarih"))
            if pd.isna(t):
                continue
            if int((bugun - t.normalize()).days) > PENCERE:
                continue
            m = _norm(o.get("olay_metni") or "")
            if any(k in m for k in OLUMSUZ_KELIMELER) or _ASLA_RE.search(m):
                olumsuz_var = True
                break

        if olumsuz_var:
            continue

        if not bulunan_sinyaller:
            continue

        tarihler = [tarih_parse(s["tarih"]) for s in bulunan_sinyaller]
        tarihler = [t for t in tarihler if not pd.isna(t)]
        if tarihler:
            son_temas_str = max(tarihler).strftime("%d.%m.%Y")
            gun_temassiz = int((bugun - max(tarihler).normalize()).days)
        else:
            son_temas_str = "-"
            gun_temassiz = 999

        olaylar = []
        for o in gecmis[:5]:
            metin = (o.get("olay_metni") or "").strip()
            if len(metin) > 400:
                metin = metin[:400] + "..."
            olaylar.append({
                "tarih": o.get("tarih", ""),
                "tip": o.get("olay_tipi", ""),
                "metin": metin,
            })

        # Sicaklik seviyesi: en guclu sinyale gore
        _SICAK_KODLAR = ("telefon_verdi", "bilgi_istedi", "is_birligi_ilgi",
                          "olumlu_yanit", "mesaj_gonderdi")
        _ILIK_KODLAR = ("baglanti_istegi", "davet_kabul")
        _kodlar = [sg["kod"] for sg in bulunan_sinyaller]
        if any(k in _kodlar for k in _SICAK_KODLAR):
            sicaklik = "SICAK"
        elif any(k in _kodlar for k in _ILIK_KODLAR):
            sicaklik = "ILIK"
        else:
            sicaklik = "-"

        sonuc.append({
            "isim": a.get("isim", "?"),
            "durum": kart.get("durum", "?"),
            "telefon": (kart.get("telefon") or "").strip(),
            "email": (kart.get("email") or "").strip(),
            "sicaklik": sicaklik,
            "sinyaller": bulunan_sinyaller,
            "sinyal_gucu": toplam_agirlik,
            "son_temas": son_temas_str,
            "gun_temassiz": gun_temassiz,
            "olaylar": olaylar,
            "_sort": -toplam_agirlik,
        })

    sonuc.sort(key=lambda x: (x["_sort"], x["gun_temassiz"]))
    return sonuc[:limit]


@bp.route("", methods=["GET"])
def hesapla():
    # v14: bloklular dahil cagir, _huni_hesapla kendi filtreler
    adaylar = adaylari_getir(bloklular_dahil=True)
    if not adaylar:
        return jsonify({"toplam": 0})
    return jsonify(_huni_hesapla(adaylar))


@bp.route("/ozet", methods=["POST"])
def ozet():
    """Girislerden (huni verisi + temassizlik suresi) CALISMA STRATEJISI,
    OLASILIK degerlendirmesi ve haftalik iletisim plani uretir.
    Rakamlar Python'da hesaplanir (asla LLM'e hesaplatilmaz), LLM sadece
    bu dogrulanmis verileri yorumlayip somut bir eylem plani cikarir."""
    adaylar = adaylari_getir()
    if not adaylar:
        return jsonify({"ozet": "Veritabanı boş, henüz bir strateji çıkarılamaz."})

    # v14: Huni bloklu adaylari da gorsun (kendi icinde filtreler)
    h = _huni_hesapla(adaylari_getir(bloklular_dahil=True))
    riskli = _riskli_adaylar(adaylar, limit=10)
    firsat = _firsat_adaylar(adaylar, limit=10)
    # Cakisma onleme: firsat listesindeki adaylar riskli listesinden cikarilsin
    _firsat_isimleri = {f["isim"].strip().lower() for f in firsat}
    riskli = [r for r in riskli if r["isim"].strip().lower() not in _firsat_isimleri]

    # Riskli adaylari DETAYLI formatta hazirla
    asama_etiket = {
        "hic_temas_yok": "HIC TEMAS EDILMEDI (sisteme kayitli, kimse aramadi)",
        "kaba_listede": "Kaba listede, sadece kayitli",
        "davet_edildi": "Davet edildi, cevap bekleniyor",
        "randevu_var": "Randevu verildi",
        "plan_yapildi": "PLAN ANLATILDI - TAKIP ASAMASI (plan gonderildi, geri bildirim bekleniyor)",
    }

    riskli_bloklar = []
    for r in riskli:
        asama_str = asama_etiket.get(r['asama'], r['asama'])
        # Iptal tespiti: son olayda iptal/duzeltme kelimesi var mi?
        _IPTAL_KEL = ("iptal", "gorusulmedi", "hatali kayit", "yanlis kayit",
                       "duzeltme", "gecersiz", "olmadi", "yapilmadi")
        _OLUMSUZ_KEL = ("ilgilenmedi", "olumsuz", "reddetti", "istemiyor",
                         "hayir dedi", "uyumsuz", "net hayir",
                         "kesinlikle hayir")
        _son_metin = (tr_norm(r["olaylar"][0]["metin"])
                       if r.get("olaylar") else "")
        _iptal_var = any(k in _son_metin for k in _IPTAL_KEL)
        _olumsuz_var = any(k in _son_metin for k in _OLUMSUZ_KEL)
        if r['gercek_temas_var']:
            baslik = f"### {r['isim']}  |  Durum: {r['durum']}  |  {r['gun_temassiz']} gundur gercek temas yok"
            baslik += f"\n  Asama: {asama_str}"
            baslik += f"\n  Son gercek temas: {r['son_gercek_temas']}"
            if _iptal_var:
                baslik += "\n  !!! SON NOT IPTAL/DUZELTME ICERIYOR - ONCEKI KAYITLAR GECERSIZ !!!"
                baslik += "\n  !!! Bu adayla GORUSULMEMIS olabilir, notlari dikkatli oku. !!!"
            if _olumsuz_var:
                baslik += "\n  !!! SON NOT OLUMSUZ - ILGI KAYBI - HAFTALIK PLANA EKLEME !!!"
        else:
            baslik = f"### {r['isim']}  |  Durum: {r['durum']}  |  HIC TEMAS EDILMEDI"
            baslik += f"\n  Sisteme kayit: {r['sisteme_kayit']} ({r['gun_temassiz']} gun once)"

        if r['telefon'] or r['email']:
            ilet = []
            if r['telefon']: ilet.append(f"Tel:{r['telefon']}")
            if r['email']: ilet.append(f"Mail:{r['email']}")
            baslik += "\n  Iletisim: " + " | ".join(ilet)
        baslik += "\n  Gecmis:"
        for o in r['olaylar']:
            baslik += f"\n    - {o['tarih']} [{o['tip']}]: {o['metin']}"
        riskli_bloklar.append(baslik)

    riskli_metin = "\n\n".join(riskli_bloklar) if riskli_bloklar else "(temassizlik verisi yok)"

    # Firsat adaylarini DETAYLI formatta hazirla
    firsat_bloklar = []
    for f_item in firsat:
        _sic = f_item.get('sicaklik', '-')
        baslik = f"### {f_item['isim']}  |  FIRSAT ADAYI  |  Sicaklik: {_sic}  |  Sinyal Gucu: {f_item['sinyal_gucu']}"
        baslik += "\n  Durum: TEMAS YAPILDI - OLUMLU SINYAL (son 7 gunde)"
        baslik += f"\n  Son temas: {f_item['son_temas']} ({f_item['gun_temassiz']} gun once)"
        if f_item['telefon'] or f_item['email']:
            ilet = []
            if f_item['telefon']: ilet.append(f"Tel:{f_item['telefon']}")
            if f_item['email']: ilet.append(f"Mail:{f_item['email']}")
            baslik += "\n  Iletisim: " + " | ".join(ilet)
        baslik += "\n  Sinyaller:"
        for sg in f_item['sinyaller']:
            baslik += f"\n    - [{sg['etiket']}] {sg['tarih']}"
        firsat_bloklar.append(baslik)

    firsat_metin = "\n\n".join(firsat_bloklar) if firsat_bloklar else "(firsat sinyali yok)"

    bugun_str = datetime.now().strftime("%d.%m.%Y (%A)")

    # Haftalik gun tablosu (bugunden baslayarak 7 gun) - Python hesaplar, LLM uydurmaz
    _TR_GUNLER = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    _bugun_ts = pd.Timestamp.now()
    _gun_satirlar = []
    for _i in range(7):
        _d = _bugun_ts + pd.Timedelta(days=_i)
        _gun_adi = _TR_GUNLER[_d.weekday()]
        _etiket = " (BUGUN)" if _i == 0 else ""
        _gun_satirlar.append(f"  Gun {_i+1}: {_d.strftime('%d.%m.%Y')} {_gun_adi}{_etiket}")
    gun_tablosu = "\n".join(_gun_satirlar)

    # v16 (Kirpma): Prompt boyutu sinirlandirildi (girinti hatasi riski sifir)
    if len(riskli_metin) > 2000:
        riskli_metin = riskli_metin[:2000] + "\n... (Cok fazla aday var, geri kalanlar gizlendi)"
    if len(firsat_metin) > 2000:
        firsat_metin = firsat_metin[:2000] + "\n... (Cok fazla aday var, geri kalanlar gizlendi)"

    # v16 (Ultimate Hizlandirma): Prompt boyutunu kesin olarak sinirla
    if len(riskli_metin) > 800:
        riskli_metin = riskli_metin[:800] + "\n... (Liste kisaltildi)"
    if len(firsat_metin) > 800:
        firsat_metin = firsat_metin[:800] + "\n... (Liste kisaltildi)"

    prompt = f"""# ROL
Sen deneyimli bir network marketing is gelistirme kocusun. Adaylarla yapilan gorusmelerin notlarini okuyup STRATEJIK oneriler veriyorsun.

# IS AKISI
kaba liste -> davet -> randevu (1:1 veya Zoom) -> plan sunumu -> kayit -> baslatma toplantisi

# KRITIK BILGI: "TEMAS" TANIMI (IHALAL EDILEMEZ)
Asagidaki olay tipleri TEMAS SAYILMAZ — bunlar sadece VERI GIRISI:
- "Excel Geçmişi"  (adayin eski verisi sisteme aktarildi)
- "Aday Kaydı"     (aday sisteme eklendi, kimse aramadi)

Yani bir adayda sadece bu olaylar varsa -> "HIC TEMAS EDILMEDI" demektir.

# KRONOLOJI VE IPTAL (COK ONEMLI)
Notlar TARIH SIRASINA gore okunur. EN SON not = GUNCEL gercek.

IPTAL/DUZELTME notu tanimi: Son notta su kelimelerden biri geciyorsa:
  "iptal", "gorusulmedi", "hatali kayit", "yanlis kayit", "duzeltme",
  "gecersiz", "olmadi", "yapilmadi"
-> Bu, ONCEKI KAYITLARIN GECERSIZ oldugu anlamina gelir.

ORNEK:
  Davet (12.10): "telefon gorusmesi yapildi, randevu olusturuldu"
  Davet (12.10): "randevu olustu"  <- flag randevu=1
  Not (12.10): "randevu iptal ... hatali kayit, adayla gorusulmedi"
  -> DOGRU OKUMA: Randevu IPTAL, adayla GORUSULMEDI.
     Yeniden temas gerekiyor, "randevu var" SAYILMAZ.
  -> YANLIS OKUMA: "randevu var, plan sunumu yap" (flag yuzunden)

KURAL: randevu=1/plan=1 flag leri SON NOT iptal iceriyorsa GECERSIZDIR.
Bu durumda "gecen gorusmemizde" gibi GECMISE ATIF YAPMA. Boyle bir gorusme OLMADI.

# HUNI VERISI (bugun: {bugun_str}) — bu rakamlar kesin, yeniden hesaplama
Toplam kaba liste: {h['toplam']}
Davet: {h['davet']}  (kaba listeden davete: %{h['oran_kabadan_davete']})
Randevu: {h['randevu']}  (davetten randevuya: %{h['oran_davetten_randevuya']})
Plan sunumu: {h['plan']}  (randevudan plana: %{h['oran_randevudan_plana']})
Kayit: {h['kayit']}  (plandan kayda: %{h['oran_plandan_kayda']})
Ucdan uca: %{h['oran_uctan_uca']}
Red orani: %{h['oran_red']}  (yumusak red: {h['hayir']}, net/blok: {h['bloklu']})
Hala surecte: {h['aktif_takipte']}

# FIRSAT ADAYLAR - YUKSEK ONCELIK (olumlu sinyaller)
Asagidaki adaylar son 7 gunde OLUMLU sinyal verdi. Ilk sirada bunlari ele al.
ONEMLI: Bu adaylar icin "Gercek temas yok" YAZMA. LinkedIn davet kabul, bilgi isteme,
telefon verme = TEMAS SAYILIR. Sicaklik ILIK ise "Sicak statusune yaklastir",
SICAK ise "Sicak statusune al" onerisi ver.
{firsat_metin}

# RİSKLI ADAYLAR - TAKIP LAZIM (notlari dahil)
{riskli_metin}

# GOREV
Asagidaki 4 basligi TURKCE uret:

**1. Huni Durumu**
Hangi adimda darbogaz var (en dusuk donusum), tek-iki cumle, rakamlarla.

**2. Aday Bazli Stratejik Oneri** (ELINDEKI ADAYLARIN TAMAMI - en az 5 DEGIL)
NOT: Elinde kac aday varsa o kadar yaz. Uydurma YASAK. Firsat + riskli havuzundan
toplam kac aday varsa (5'ten az olsa bile) hepsini ele al.
ONCE FIRSAT adaylarindan basla (olumlu sinyal verenler), sonra riskli adaylara gec.
NOT: Bu bolumde HAFTALIK PLAN YAZMA. Sadece aday-aksiyon listesi ver.
Her aday icin:
- **Durum**: 1 cumle (gercek temas var mi, yok mu — buna gore cumle kur)
- **Yorum**: Adayin notundan cikarim (meslegi, motivasyonu, ilgisi)
- **Aksiyon**: Bugun/yarin tam olarak ne yapilmali
- **Mesaj metni onerisi**:
  * HIC TEMAS YOKSA → "tanisma mesaji" tonu:
    "Merhaba X Hanim/Bey, sizi [sebep] dolayisiyla ekibimize dahil etmek istiyoruz. Müsait oldugunuzda kisa bir gorusme planlayabilir miyiz?"
  * GECMIS TEMAS VARSA → samimi takip tonu.

**3. Bugünkü Günlük Çalışma Stratejisi (SADECE BUGÜN)**
ONEMLI: SADECE BUGUN için yapilmasi gereken 3-5 stratejik aksiyon yaz. Haftalik plan, gelecek hafta YASAK.
{gun_tablosu}

KURALLAR:
- Her gunu tablodaki TARIH ve GUN ADI ile yaz (kopyala, UYDURMA).
- Tablodaki sirayi takip et (Gun 1, Gun 2, ... Gun 7).
- HER GUNUN ALTINA aday adi + somut aksiyon yaz. Sadece tablo yetmez, aksiyon ZORUNLU.
- 7 GUNUN HEPSI DOLU OLMALI. Bos gun BIRAKMA.
- Aday yetmezse: bir adayi farkli gunde tekrar kullan veya "Takip: genel kontrol" yaz.
  Ornek format:
    ### Gun 1: <TARIH> <GUN_ADI> (BUGUN)
    - <Aday Adi>: <Somut aksiyon>
    ### Gun 2: <TARIH> <GUN_ADI>
    - <Aday Adi>: <Somut aksiyon>
    (Bu sekilde 7 gune kadar devam et, HER GUN DOLU)
    NOT: Tarihleri YUKARIDAKI HAFTALIK TABLODAN al, kendin uydurma.
- Son notu OLUMSUZ olan adaylari ("ilgilenmedi", "olumsuz", "reddetti") plana EKLEME.
- Once FIRSAT adaylarindan basla, sonra riskli adaylara gec.

**4. Gozden Kacan Firsatlar**
Huni verisinde anomali veya firsat var mi?
ONEMLI: Yukarida (bolum 2 ve 3) zaten yazdigin adaylari TEKRARLAMA.
Sadece yukarida DEGINILMEYEN firsatlari listele. Yeni firsat yoksa "Yeni firsat yok" yaz.

YAZIM KURALLARI (ZORUNLU):
- "fırsat" yaz (fırst degil)
- "müsait" yaz (musait degil)
- "teşekkür" yaz (tesekkur degil)
- "görüşme" yaz (gorusme degil)
- Tum cumlelerde Turkce karakterleri DOGRU kullan.

# KURALLAR (IHALAL EDILEMEZ)
1. SADECE TURKCE. Tek kelime bile Ingilizce/Cince YAZMA.
2. Rakam UYDURMA, verilen rakamlari kullan.
3. Aday isimlerini notlardan al, uydurma.
4. HALUSINASYON YASAGI: "gecen gorusmemizde", "onceki konusmamizda", "bahsettigimiz gibi" gibi ifadeler SADECE notta ACIKCA yaziyorsa kullanilabilir. Emin degilsen KULLANMA. Notta "gorusulmedi" yaziyorsa HIC KULLANMA.
5. Somut ol. "Iletisime gec" yerine NE SOYLEYECEGINI yaz.
6. LaTeX/Markdown matematik YASAK.
7. Toplam 25-35 satir.
8. YAZIM KONTROLU: yarinrandaki yerine yarinki, firsa yerine firsat, musait yerine müsait, gorusmeme yerine gorusmeye. Nokta-virgul karistirma."""

    # v16: JSON Structured Output icin prompt eki
    prompt += """

# CIKTI FORMATI (COK ONEMLI - SADECE JSON DONDUR)
Cevabini SADECE asagidaki JSON formatinda ver. Baska hicbir aciklama, giris veya bitis cumlesi yazma. Markdown kullanma.
{
  "huni_durumu": "Huni ile ilgili 2-3 cumlelik stratejik yorum.",
  "aday_onerileri": [
    {"isim": "Aday Adi", "durum": "Aday Durumu", "aksiyon": "Tam olarak ne yapilmali"}
  ],
  "bugunku_plan": [
    {"saat": "Sabah", "aksiyon": "Bugun yapilacak aksiyon"}
  ],
  "gozden_kacanlar": "Gozden kacan firsatlar veya riskler."
}
"""

    try:
        # v16: Prompt boyutunu olcelim
        print(f"[METRICS] Prompt Uzunlugu: {len(prompt)} karakter")
        print(f"[METRICS] Ilk 500 karakter: {prompt[:500]}...")
        
        metin = ""
        for parca in chat_stream([{"role": "user", "content": prompt}],
                                  model=CHAT_MODEL, fallback=DEFAULT_FALLBACK,  # v17: 14B yerine 7B
                                  profil="analiz", format="json"):
            metin += parca
            
        raw_metin = metin.strip()
        json_veri = None
        
        # v16: JSON blogunu ayikla
        import json as _json
        import re
        try:
            # Model ```json ... ``` seklinde markdown kullandiysa temizle
            clean_metin = re.sub(r'^```json\s*', '', raw_metin, flags=re.MULTILINE)
            clean_metin = re.sub(r'```\s*$', '', clean_metin, flags=re.MULTILINE)
            
            # Ilk { ile son } arasini al
            start_idx = clean_metin.find("{")
            end_idx = clean_metin.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = clean_metin[start_idx:end_idx+1]
                
                import re
                def _extract_json_fallback(js):
                    d = {}
                    # ozet
                    m_ozet = re.search(r'"(?:ozet|huni_durumu)"\s*:\s*"(.*?)"(?:,|\n|\})', js, re.DOTALL)
                    if m_ozet: d["ozet"] = m_ozet.group(1).replace('\\n', '\n')
                    
                    # adaylar
                    m_adaylar = re.search(r'"(?:oncelikli_adaylar|aday_onerileri)"\s*:\s*\[(.*?)\]', js, re.DOTALL)
                    if m_adaylar:
                        d["oncelikli_adaylar"] = []
                        for item in re.finditer(r'\{(.*?)\}', m_adaylar.group(1), re.DOTALL):
                            a = {}
                            m_isim = re.search(r'"isim"\s*:\s*"(.*?)"', item.group(1))
                            if m_isim: a["isim"] = m_isim.group(1)
                            m_durum = re.search(r'"durum"\s*:\s*"(.*?)"', item.group(1))
                            if m_durum: a["durum"] = m_durum.group(1)
                            m_aksiyon = re.search(r'"aksiyon"\s*:\s*"(.*?)"', item.group(1))
                            if m_aksiyon: a["aksiyon"] = m_aksiyon.group(1)
                            if a: d["oncelikli_adaylar"].append(a)
                            
                    # plan
                    m_plan = re.search(r'"(?:bugunku_plan|haftalik_plan)"\s*:\s*\[(.*?)\]', js, re.DOTALL)
                    if m_plan:
                        d["bugunku_plan"] = []
                        for item in re.finditer(r'\{(.*?)\}', m_plan.group(1), re.DOTALL):
                            p = {}
                            m_saat = re.search(r'"(?:saat|gun)"\s*:\s*"(.*?)"', item.group(1))
                            if m_saat: p["saat"] = m_saat.group(1)
                            m_aksiyon = re.search(r'"(?:aksiyon|gorevler)"\s*:\s*\[?\s*"(.*?)"', item.group(1))
                            if m_aksiyon: p["aksiyon"] = m_aksiyon.group(1)
                            if p: d["bugunku_plan"].append(p)
                            
                    # gozden kacanlar
                    m_gozden = re.search(r'"gozden_kacanlar"\s*:\s*\[(.*?)\]', js, re.DOTALL)
                    if m_gozden:
                        d["gozden_kacanlar"] = re.findall(r'"(.*?)"', m_gozden.group(1))
                        
                    return d

                try:
                    json_veri = _json.loads(json_str)
                except Exception as e_json:
                    print(f"[JSON] Parse hatasi: {e_json} - Regex yedegi devrede.")
                    json_veri = _extract_json_fallback(json_str)
                
                # v16 (Normalizasyon): Eski JSON anahtarlarini yenilerine cevir
                if "huni_durumu" in json_veri and "ozet" not in json_veri:
                    json_veri["ozet"] = json_veri["huni_durumu"]
                if "aday_onerileri" in json_veri and "oncelikli_adaylar" not in json_veri:
                    json_veri["oncelikli_adaylar"] = json_veri["aday_onerileri"]
                if "haftalik_plan" in json_veri and "bugunku_plan" not in json_veri: # v18 Guvenli Gunluk Plan
                    # Haftalik plani bugunku plan formatina uyarla
                    json_veri["bugunku_plan"] = []
                    for item in json_veri.get("haftalik_plan", []):
                        gun = item.get("gun", "")
                        for gorev in item.get("gorevler", []):
                            json_veri["bugunku_plan"].append({"saat": gun, "aksiyon": gorev})
                
                print("[JSON] Basariyla parse edildi (Normalize edildi).")
                print("--- MODEL CIKTISI (DEBUG) ---")
                print(json_str[:1500]) # İlk 1500 karakteri ekrana bas
                print("-----------------------------")
            else:
                print("[JSON] JSON blogu bulunamadi, raw metin donuyor.")
        except Exception as e_json:
            print(f"[JSON PARSE HATASI] {e_json}")

        return jsonify({"ozet": raw_metin, "json_veri": json_veri, "huni": h})
    except Exception as e:
        return jsonify({"ozet": f"Strateji oluşturulamadı: {e}"}), 500


@bp.route("/hatirlatmalar", methods=["GET"])
def hatirlatmalar():
    """v17: Akilli Hatirlatma Motoru"""
    from core.database import akilli_hatirlatmalar_getir
    return jsonify(akilli_hatirlatmalar_getir())

@bp.route("/son-gelismeler", methods=["GET"])
def son_gelismeler():
    from core.database import son_gelismeler_getir
    return jsonify(son_gelismeler_getir())





from flask import Response, request

@bp.route("/takvim", methods=["GET"])
def takvim_indir():
    """Randevulari .ics (iCalendar) formatinda indirir."""
    import datetime
    from urllib.parse import unquote
    
    isim = unquote(request.args.get("isim", "Aday"))
    tarih_str = request.args.get("tarih", "")
    
    if not tarih_str:
        return "Tarih belirtilmedi", 400

    try:
        if "-" in tarih_str:
            _d = datetime.datetime.strptime(tarih_str[:10], "%Y-%m-%d")
        elif "." in tarih_str:
            _d = datetime.datetime.strptime(tarih_str, "%d.%m.%Y")
        else:
            _d = datetime.datetime.now()
    except Exception:
        _d = datetime.datetime.now()

    dt_start = _d.strftime("%Y%m%dT090000")
    dt_end = _d.strftime("%Y%m%dT100000")
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AI_YEREL//LinkedIn Takip Asistani//TR
BEGIN:VEVENT
SUMMARY:Randevu - {isim}
DTSTART:{dt_start}
DTEND:{dt_end}
DESCRIPTION:LinkedIn Takip Asistani uzerinden olusturulan randevu.
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=randevu_{isim.replace(' ', '_')}.ics"}
    )
