import sqlite3
from datetime import datetime
from config import ADAY_DB, CHAT_DB, ADAY_STATULERI


def _statu_adi(kod):
    """config.ADAY_STATULERI'ndan tam statu string'ini dondurur.
    Ornek: _statu_adi('sg') -> '🎓 SG'"""
    for s in ADAY_STATULERI:
        if s["kod"] == kod:
            return s["tam"]
    return kod  # bulunamazsa kodu oldugu gibi don



def _profil_id_eski_aday(aday_id):
    """Eski aday ID'sinden profil ID'sini bulur."""
    with _conn(ADAY_DB) as c:
        # 1. aday_olaylari tablosunda ara
        row = c.execute(
            """
            SELECT aday_id
            FROM aday_olaylari
            WHERE kaynak_kayit_id = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (aday_id,)
        ).fetchone()

        if row:
            return row["aday_id"]

        # 2. isim ile aday_profil'da ara
        eski = c.execute(
            "SELECT isim FROM adaylar WHERE id=?",
            (aday_id,)
        ).fetchone()

        if not eski:
            return None

        isim = eski["isim"] or ""

        # 3. Ayni isimdeki profil kaydini bul
        profil = c.execute(
            "SELECT id FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
            (aday_id, isim,)
        ).fetchone()

        if profil:
            return profil["id"]

        return None

def _conn(db_path):
    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        timeout=10
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return conn


def hash_silinmis_mi(kaynak_hash):
    if not kaynak_hash:
        return False
    with _conn(ADAY_DB) as c:
        row = c.execute("SELECT 1 FROM silinen_hashler WHERE kaynak_hash=?", (kaynak_hash,)).fetchone()
        return row is not None

def _kolon_ekle(conn, tablo, kolon, tip):
    mevcut = {
        r["name"]
        for r in conn.execute(f"PRAGMA table_info({tablo})").fetchall()
    }
    if kolon not in mevcut:
        conn.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tip}")
        return True
    return False


def init_all():
    # --------------------------------------------------------
    # Eski aday tablosu - mevcut Excel/AI sistemi korunuyor.
    # --------------------------------------------------------
    with _conn(ADAY_DB) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS adaylar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT,
            tarih TEXT,
            aciklama TEXT,
            davet INTEGER,
            randevu INTEGER,
            plan INTEGER,
            kayit INTEGER,
            takip INTEGER,
            hayir INTEGER,
            is_ariyor INTEGER,
            kaynak_hash TEXT UNIQUE,
    linkedin_url TEXT
        )''')

        # ----------------------------------------------------
        # Yeni aday profili
        # ----------------------------------------------------
        c.execute('''
            CREATE TABLE IF NOT EXISTS aday_profil (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isim TEXT NOT NULL,
                telefon TEXT DEFAULT '',
                email TEXT DEFAULT '',
                adres TEXT DEFAULT '',
                durum TEXT DEFAULT '',         -- v11 D2
                aktif INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        ''')

        # ----------------------------------------------------
        # Yeni aday olay/gecmis tablosu
        # ----------------------------------------------------
        c.execute('''
            CREATE TABLE IF NOT EXISTS aday_olaylari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aday_id INTEGER NOT NULL,
                tarih TEXT,
                olay_tipi TEXT,
                olay_metni TEXT,
                kaynak TEXT,
                kaynak_kayit_id INTEGER,
                davet INTEGER DEFAULT 0,
                randevu INTEGER DEFAULT 0,
                plan INTEGER DEFAULT 0,
                kayit INTEGER DEFAULT 0,
                takip INTEGER DEFAULT 0,
                hayir INTEGER DEFAULT 0,
                is_ariyor INTEGER DEFAULT 0,
                durum TEXT DEFAULT '',
                created_at TEXT
            )
        ''')

        # Önceden migration yapılmış sistemlerde durum kolonu yoksa ekle.
        _kolon_ekle(c, "aday_olaylari", "durum", "TEXT DEFAULT ''")
        _kolon_ekle(c, "aday_profil", "durum", "TEXT DEFAULT ''")  # v11 D2
        _kolon_ekle(c, "aday_profil", "aday_id", "INTEGER")     # v16 D23
        _kolon_ekle(c, "aday_profil", "ai_oneri_durum", "TEXT DEFAULT ''")
        _kolon_ekle(c, "aday_profil", "ai_oneri_not", "TEXT DEFAULT ''")
        _kolon_ekle(c, "adaylar", "blok", "INTEGER DEFAULT 0")
        _kolon_ekle(c, "adaylar", "blok_tarihi", "TEXT")
        _kolon_ekle(c, "adaylar", "blok_notu", "TEXT")
        _kolon_ekle(c, "adaylar", "linkedin_url", "TEXT")
        _kolon_ekle(c, "adaylar", "randevu_tarihi", "TEXT")
        _kolon_ekle(c, "adaylar", "randevu_saati", "TEXT")

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_aday_profil_isim
            ON aday_profil(isim)
        ''')

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_aday_olaylari_aday
            ON aday_olaylari(aday_id)
        ''')

        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_aday_olaylari_tarih
            ON aday_olaylari(tarih)
        ''')

        # ----------------------------------------------------
        # Migration kontrolü:
        # Eski adaylar için profil + eski Excel geçmişi oluştur.
        # Daha önce yapılmış migration tekrar kayıt üretmez.
        # ----------------------------------------------------
        eski_adaylar = c.execute(
            "SELECT * FROM adaylar ORDER BY id ASC"
        ).fetchall()

        for eski in eski_adaylar:
            isim = (eski["isim"] or "").strip()
            if not isim:
                continue

            profil = c.execute(
                '''
                SELECT id
                FROM aday_profil
                WHERE lower(trim(isim)) = lower(trim(?))
                ORDER BY id ASC
                LIMIT 1
                ''',
                (isim,)
            ).fetchone()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if profil is None:
                cur = c.execute(
                    '''
                    INSERT INTO aday_profil
                    (isim, telefon, email, adres, durum, aktif, created_at, updated_at, aday_id)
                    VALUES (?, '', '', '', ?, 1, ?, ?, ?)
                    ''',
                    (isim.strip(), "🆕 Yeni", now, now, aday_id)
                )
                profil_id = cur.lastrowid
            else:
                profil_id = profil["id"]

            mevcut_olay = c.execute(
                '''
                SELECT id
                FROM aday_olaylari
                WHERE kaynak = 'excel_migrasyon'
                  AND kaynak_kayit_id = ?
                LIMIT 1
                ''',
                (eski["id"],)
            ).fetchone()

            if mevcut_olay is None:
                c.execute(
                    '''
                    INSERT INTO aday_olaylari
                    (
                        aday_id,
                        tarih,
                        olay_tipi,
                        olay_metni,
                        kaynak,
                        kaynak_kayit_id,
                        davet,
                        randevu,
                        plan,
                        kayit,
                        takip,
                        hayir,
                        is_ariyor,
                        durum,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        profil_id,
                        eski["tarih"] or "",
                        "Excel Geçmişi",
                        eski["aciklama"] or "",
                        "excel_migrasyon",
                        eski["id"],
                        int(eski["davet"] or 0),
                        int(eski["randevu"] or 0),
                        int(eski["plan"] or 0),
                        int(eski["kayit"] or 0),
                        int(eski["takip"] or 0),
                        int(eski["hayir"] or 0),
                        int(eski["is_ariyor"] or 0),
                        "",
                        now
                    )
                )

        c.commit()

    # --------------------------------------------------------
    # Chat geçmişi
    # --------------------------------------------------------
    with _conn(CHAT_DB) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS sohbet_loglari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rol TEXT,
            icerik TEXT,
            zaman TEXT,
            model TEXT,
            fallback INTEGER DEFAULT 0
        )''')

        mevcut = {
            r["name"]
            for r in c.execute(
                "PRAGMA table_info(sohbet_loglari)"
            ).fetchall()
        }

        if "model" not in mevcut:
            c.execute(
                "ALTER TABLE sohbet_loglari ADD COLUMN model TEXT"
            )

        if "fallback" not in mevcut:
            c.execute(
                "ALTER TABLE sohbet_loglari ADD COLUMN fallback INTEGER DEFAULT 0"
            )

        if "kategori" not in mevcut:
            c.execute(
                "ALTER TABLE sohbet_loglari ADD COLUMN kategori TEXT DEFAULT 'sohbet'"
            )
            # Mevcut mesajlari geriye donuk kategorize et
            print("Mevcut mesajlar kategorize ediliyor...")
            tum_mesajlar = c.execute(
                "SELECT id, rol, icerik FROM sohbet_loglari"
            ).fetchall()
            for m in tum_mesajlar:
                k = _kategori_bul(m["icerik"], m["rol"])
                c.execute(
                    "UPDATE sohbet_loglari SET kategori=? WHERE id=?",
                    (k, m["id"])
                )
            print(f"{len(tum_mesajlar)} mesaj kategorize edildi")

        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_sohbet_kategori ON sohbet_loglari(kategori)"
        )

        c.commit()


# ============================================================
# Eski aday sistemi
# ============================================================

def adaylari_getir(bloklular_dahil=False):
    """Tum adaylari son durumlariyla birlikte dondurur.
    Durum, aday_profil tablosundan okunur (kart ile ayni kaynak).
    bloklular_dahil=False ise blok=1 olanlar haric tutulur."""
    with _conn(ADAY_DB) as c:
        if bloklular_dahil:
            rows = c.execute("SELECT * FROM adaylar ORDER BY id DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM adaylar WHERE COALESCE(blok, 0) = 0 ORDER BY id DESC"
            ).fetchall()

        sonuc = []
        for r in rows:
            d = dict(r)
            isim = (d.get("isim") or "").strip()

            # Durum: aday_profil'DAN (kart ile ayni kaynak)
            durum = "Değerlendirilecek"
            try:
                if isim:
                    profil = c.execute(
                        "SELECT durum FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
                        (d.get("id"), isim,)
                    ).fetchone()
                    
                    if profil and profil["durum"]:
                        durum = profil["durum"]
                    else:
                        durum = "Değerlendirilecek"
            except Exception:
                durum = "Değerlendirilecek"

            # Açıklama: en son gelişme metni (varsa)
            try:
                son_olay = c.execute(
                    """
                    SELECT olay_metni FROM aday_olaylari
                    WHERE kaynak_kayit_id = ?
                      AND olay_metni IS NOT NULL
                      AND olay_metni != ''
                    ORDER BY id DESC  -- v19 Kronoloji Fix
                    LIMIT 1
                    """,
                    (r["id"],)
                ).fetchone()
                if son_olay and son_olay["olay_metni"]:
                    d["aciklama"] = son_olay["olay_metni"]
            except Exception:
                pass

            d["durum"] = durum
            sonuc.append(d)

    return sonuc

def aday_ekle(
    isim,
    tarih,
    aciklama,
    davet,
    randevu,
    plan,
    kayit,
    takip,
    hayir,
    is_ariyor,
    kaynak_hash=None,
    linkedin_url=None,
    durum=""
):
    try:
        with _conn(ADAY_DB) as c:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Blok kontrolü: aynı isimde bloklu aday varsa atla
            if isim and isim.strip():
                bloklu = c.execute(
                    "SELECT id FROM adaylar WHERE lower(trim(isim)) = lower(trim(?)) AND COALESCE(blok,0)=1 LIMIT 1",
                    (isim.strip(),)
                ).fetchone()
                if bloklu:
                    print(f"[BLOK] '{isim}' bloklu listede, atlandi (id={bloklu['id']})")
                    return False

            c.execute(
                '''
                INSERT INTO adaylar
                (
                    isim,
                    tarih,
                    aciklama,
                    davet,
                    randevu,
                    plan,
                    kayit,
                    takip,
                    hayir,
                    is_ariyor,
                    kaynak_hash,
                    linkedin_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    isim,
                    tarih,
                    aciklama,
                    int(davet),
                    int(randevu),
                    int(plan),
                    int(kayit),
                    int(takip),
                    int(hayir),
                    int(is_ariyor),
                    kaynak_hash,
                    linkedin_url
                )
            )

            eski_id = c.execute(
                "SELECT last_insert_rowid() AS id"
            ).fetchone()["id"]

            profil = c.execute(
                '''
                SELECT id
                FROM aday_profil
                WHERE lower(trim(isim)) = lower(trim(?))
                ORDER BY id ASC
                LIMIT 1
                ''',
                (isim.strip(),)
            ).fetchone()

            if profil is None:
                cur = c.execute(
                    '''
                    INSERT INTO aday_profil
                    (isim, telefon, email, adres, durum, aktif, created_at, updated_at, aday_id)
                    VALUES (?, '', '', '', ?, 1, ?, ?, ?)
                    ''',
                    (isim.strip(), durum or "🆕 Yeni", now, now, eski_id)
                )
                profil_id = cur.lastrowid
            else:
                profil_id = profil["id"]

            c.execute(
                '''
                INSERT INTO aday_olaylari
                (
                    aday_id,
                    tarih,
                    olay_tipi,
                    olay_metni,
                    kaynak,
                    kaynak_kayit_id,
                    davet,
                    randevu,
                    plan,
                    kayit,
                    takip,
                    hayir,
                    is_ariyor,
                    durum,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    profil_id,
                    tarih or "",
                    "Aday Kaydı",
                    aciklama or "",
                    "uygulama",
                    eski_id,
                    int(davet),
                    int(randevu),
                    int(plan),
                    int(kayit),
                    int(takip),
                    int(hayir),
                    int(is_ariyor),
                    durum or "",
                    now
                )
            )

            c.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    except Exception as e:
        print(f"Aday ekleme hatası: {e}")
        return False

def aday_sil(aday_id):
    """Adayi ve TUM bagli kayitlarini siler (cascade).

    v11 D1: adaylar.id -> aday_olaylari.kaynak_kayit_id,
            aday_olaylari.aday_id -> aday_profil.id
    """
    with _conn(ADAY_DB) as c:
        # 1. Ismi al
        row = c.execute(
            "SELECT isim, kaynak_hash FROM adaylar WHERE id=?",
            (aday_id,)
        ).fetchone()

        if not row:
            return False

        isim = (row["isim"] or "").strip()
        khash = row["kaynak_hash"]
        if khash:
            from datetime import datetime
            c.execute("INSERT OR IGNORE INTO silinen_hashler (kaynak_hash, silinme_tarihi) VALUES (?, ?)", 
                      (khash, datetime.now().isoformat()))

        # 2. Bu adayin profil_id'sini bul
        profil_id = None
        if isim:
            profil_row = c.execute(
                "SELECT id FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
                (aday_id, isim,)
            ).fetchone()
            if profil_row:
                profil_id = profil_row["id"]

        # 3. aday_olaylari sil (iki yonlu)
        c.execute("DELETE FROM aday_olaylari WHERE kaynak_kayit_id=?", (aday_id,))
        if profil_id is not None:
            c.execute("DELETE FROM aday_olaylari WHERE aday_id=?", (profil_id,))

        # 4. aday_profil sil
        if profil_id is not None:
            c.execute("DELETE FROM aday_profil WHERE id=?", (profil_id,))

        # 5. adaylar sil
        c.execute("DELETE FROM adaylar WHERE id=?", (aday_id,))

        c.commit()
        return True


def tum_adaylari_sil():
    """v14: TUM aday verilerini siler + ID'leri sifirlar.

    Silinen tablolar (bagimlidan koke dogru):
      - aday_olaylari
      - aday_profil
      - adaylar

    Ayrica sqlite_sequence sifirlanir, boylece yeni eklenen adaylar
    id=1'den baslar (UI sira no ile DB id uyumu icin).
    """
    with _conn(ADAY_DB) as c:
        c.execute("DELETE FROM silinen_hashler")
        c.execute("DELETE FROM aday_olaylari")
        c.execute("DELETE FROM aday_profil")
        c.execute("DELETE FROM adaylar")

        # sqlite_sequence AUTOINCREMENT kullanan tablolar icin var.
        # Bos DB'de henuz olusmamis olabilir -> once kontrol et.
        seq_var = c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if seq_var:
            c.execute(
                "DELETE FROM sqlite_sequence "
                "WHERE name IN ('adaylar', 'aday_profil', 'aday_olaylari')"
            )

        c.commit()


# ============================================================
# Yeni Aday Kartı / Geçmiş sistemi
# ============================================================

def aday_karti_getir(eski_aday_id):
    """Eski aday ID'sinden kart bilgilerini getirir."""
    with _conn(ADAY_DB) as c:
        # 1. adaylar tablosundan ana kaydi al
        eski = c.execute(
            "SELECT * FROM adaylar WHERE id=?",
            (eski_aday_id,)
        ).fetchone()

        if not eski:
            return None

        isim = eski["isim"] or ""

        # 2. Profil bilgileri (varsa) - v18 Kart Liste Senkron
        profil = c.execute(
            "SELECT * FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
            (aday_id, isim,)
        ).fetchone()

        # 3. Son durum: ONCE PROFILDEN OKU, yoksa OLAYLARA bak
        durum = "⚪ Değerlendirilecek"
        
        # Profil tablosunda durum varsa onu kullan (tek dogruluk kaynagi)
        if profil and profil["durum"]:
            durum = profil["durum"]
        else:
            # Profilde yoksa olay gecmisinden son durumu bul
            durum_row = c.execute("""
                SELECT durum FROM aday_olaylari
                WHERE kaynak_kayit_id = ?
                  AND durum IS NOT NULL
                  AND durum != ''
                ORDER BY id DESC LIMIT 1
            """, (eski_aday_id,)).fetchone()
            
            if durum_row and durum_row["durum"]:
                durum = durum_row["durum"]

        # 4. Gecmis olaylar
        gecmis = []
        try:
            gecmis_rows = c.execute("""
                SELECT tarih, olay_tipi, olay_metni, durum
                FROM aday_olaylari
                WHERE kaynak_kayit_id = ?
                ORDER BY id DESC  -- v19 Kronoloji Fix
                LIMIT 50
            """, (eski_aday_id,)).fetchall()
            gecmis = [dict(r) for r in gecmis_rows]
        except Exception:
            gecmis = []

        def _get(row, key, default=None):
            try:
                return row[key] if row and key in row.keys() else default
            except Exception:
                return default

        return {
            "id": eski["id"],
            "isim": isim,
            "tarih": _get(eski, "tarih", ""),
            "aciklama": _get(eski, "aciklama", ""),
            "davet": _get(eski, "davet", 0),
            "randevu": _get(eski, "randevu", 0),
            "plan": _get(eski, "plan", 0),
            "kayit": _get(eski, "kayit", 0),
            "takip": _get(eski, "takip", 0),
            "hayir": _get(eski, "hayir", 0),
            "is_ariyor": _get(eski, "is_ariyor", 0),
            "linkedin_url": _get(eski, "linkedin_url", None),
            "telefon": _get(profil, "telefon", ""),
            "email": _get(profil, "email", ""),
            "adres": _get(profil, "adres", ""),
            "durum": durum,
            "gecmis": gecmis,
            # v17 Randevu Backend Fix
            "randevu_tarihi": _get(eski, "randevu_tarihi", ""),
            "randevu_saati": _get(eski, "randevu_saati", "")
        }

def aday_profil_guncelle(aday_id, telefon, email, adres):
    """Aday profil bilgilerini gunceller (telefon, email, adres)."""
    with _conn(ADAY_DB) as c:
        # 1. Adayin ismini al
        eski = c.execute(
            "SELECT isim FROM adaylar WHERE id=?",
            (aday_id,)
        ).fetchone()

        if not eski:
            return False

        isim = eski["isim"] or ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Bu isimde profil var mi?
        profil = c.execute(
            "SELECT id FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
            (aday_id, isim,)
        ).fetchone()

        if profil:
            # 3a. Varsa guncelle
            c.execute(
                """
                UPDATE aday_profil
                SET telefon=?, email=?, adres=?, updated_at=?
                WHERE id=?
                """,
                (telefon, email, adres, now, profil["id"])
            )
        else:
            # 3b. Yoksa yeni olustur
            c.execute(
                """
                INSERT INTO aday_profil
                (isim, telefon, email, adres, aktif, created_at, updated_at, aday_id)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (isim, telefon, email, adres, now, now, aday_id)
            )

        c.commit()
        return True

def aday_gelisme_ekle(
    eski_aday_id,
    tarih,
    olay_tipi,
    olay_metni,
    durum="",
    blok=0
):
    with _conn(ADAY_DB) as c:
        profil_id = _profil_id_eski_aday(eski_aday_id)

        if profil_id is None:
            return False, "Aday bulunamadı."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        c.execute(
            '''
            INSERT INTO aday_olaylari
            (
                aday_id,
                tarih,
                olay_tipi,
                olay_metni,
                kaynak,
                kaynak_kayit_id,
                davet,
                randevu,
                plan,
                kayit,
                takip,
                hayir,
                is_ariyor,
                durum,
                created_at
            )
            VALUES (?, ?, ?, ?, 'uygulama', ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)
            ''',
            (
                profil_id,
                tarih or "",
                olay_tipi or "Not",
                olay_metni or "",
                eski_aday_id,
                durum or "",
                now
            )
        )

        # Durum verildiyse aday_profil.durum'u da guncelle
        if durum and str(durum).strip():
            try:
                isim_row = c.execute(
                    "SELECT isim FROM adaylar WHERE id=?",
                    (eski_aday_id,)
                ).fetchone()

                if isim_row:
                    try:
                        isim = isim_row["isim"] if hasattr(isim_row, "keys") else isim_row[0]
                    except Exception:
                        isim = str(isim_row)
                    isim = (isim or "").strip()

                    if isim:
                        profil = c.execute(
                            "SELECT id FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
                            (aday_id, isim,)
                        ).fetchone()

                        if profil:
                            try:
                                pid = profil["id"] if hasattr(profil, "keys") else profil[0]
                            except Exception:
                                pid = profil
                            c.execute(
                                "UPDATE aday_profil SET durum=?, updated_at=? WHERE id=?",
                                (durum, now, pid)
                            )
                        else:
                            c.execute(
                                "INSERT INTO aday_profil (isim, telefon, email, adres, durum, aktif, created_at, updated_at, aday_id) VALUES (?, '', '', '', ?, 1, ?, ?, ?)",
                                (isim, durum, now, now, aday_id)
                            )
            except Exception as e:
                print(f"Durum guncelleme hatasi: {e}")


        # Blok işlemi
        if blok == 1:
            c.execute(
                "UPDATE adaylar SET blok=1, blok_tarihi=?, blok_notu=? WHERE id=?",
                (now, olay_metni or "", eski_aday_id)
            )

        c.commit()

    return True, "Gelişme kaydedildi."


# ============================================================
# Chat İşlemleri
# ============================================================

def _kategori_bul(mesaj, rol):
    """Mesaji keyword bazli kategorize eder.
    Kategoriler: sohbet, istatistik, sorgu, oneri, analiz
    Oncelik sirasi: oneri > analiz > istatistik > sorgu > sohbet
    """
    if not mesaj:
        return "sohbet"

    m = mesaj.lower()
    # Turkce karakter normalizasyonu
    tr_map = str.maketrans("İIıçşğüöÇŞĞÜÖ", "iiicsguoCSGUO")
    m = mesaj.translate(tr_map).lower()
    if rol == "assistant":
        # Cevap icerigi bazli
        if "oneri:" in m or "aksiyon:" in m:
            return "oneri"
        if any(k in m for k in ["funnel", "analiz", "trend", "oran", "donusum"]):
            return "analiz"
        return "sohbet"

    # Kullanici mesaji - ONERI once (daha guclu sinyal)
    if any(k in m for k in ["degerlendir", "oner", "odaklan", "oncelik",
                            "strateji", "planla", "yapalim", "yapmali",
                            "ne yap", "nasil ilerle", "kimlere odak"]):
        return "oneri"
    # ANALIZ
    if any(k in m for k in ["analiz", "funnel", "trend", "karsilastir", "rapor"]):
        return "analiz"
    # ISTATISTIK
    if any(k in m for k in ["kac", "toplam", "sayi", "adet", "liste", "kactane"]):
        return "istatistik"
    # SORGU
    if any(k in m for k in ["kim", "nerede", "hangi", "ne zaman", "baska", "neler"]):
        return "sorgu"
    return "sohbet"


def chat_mesajlari_getir():
    with _conn(CHAT_DB) as c:
        rows = c.execute(
            '''
            SELECT rol, icerik, zaman, model, fallback, kategori
            FROM sohbet_loglari
            ORDER BY id ASC
            '''
        ).fetchall()

    return [
        {
            "role": r["rol"],
            "content": r["icerik"],
            "zaman": r["zaman"],
            "model": r["model"],
            "fallback": bool(r["fallback"]),
            "kategori": r["kategori"] or "sohbet"
        }
        for r in rows
    ]


def chat_mesaj_ekle(
    rol,
    icerik,
    model=None,
    fallback=False,
    kategori=None
):
    # Kategori verilmediyse otomatik bul
    if kategori is None:
        kategori = _kategori_bul(icerik, rol)

    with _conn(CHAT_DB) as c:
        c.execute(
            '''
            INSERT INTO sohbet_loglari
            (rol, icerik, zaman, model, fallback, kategori)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                rol,
                icerik,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                model,
                int(bool(fallback)),
                kategori
            )
        )
        c.commit()


def chat_temizle():
    with _conn(CHAT_DB) as c:
        c.execute("DELETE FROM sohbet_loglari")
        c.commit()



def aday_linkedin_guncelle(aday_id, linkedin_url):
    """Adayin LinkedIn URL'sini gunceller."""
    with _conn(ADAY_DB) as c:
        c.execute(
            "UPDATE adaylar SET linkedin_url=? WHERE id=?",
            (linkedin_url, aday_id)
        )
        c.commit()
        return c.total_changes > 0



def aday_durum_otomatik_guncelle(aday_id, davet=0, plan=0, kayit=0, hayir=0, net_hayir=0):
    
    """Checkbox'lara gore statuyu otomatik gunceller.

    v7 4C-2: DB'deki MEVCUT bayraklar da okunur. Boylece bir aday
    once plan yapmis, sonra kayit yapmissa, kayit olayinda plan=0
    gelse bile DB'de plan=1 kaldigi icin "plan+kayit -> SG" gecisi
    dogru tetiklenir.

    Kurallar:
    - Hayir -> Otomatik atama YOK (manuel secim: DeepFreeze veya Blok)
    - Plan ✓ + Kayit ✓ -> 🎓 SG
    - Plan ✓ + Kayit ✗ -> 🔔 Takip
    - Plan ✗ + Davet ✓ -> 🟢 Aktif
    """
    with _conn(ADAY_DB) as c:
        eski = c.execute(
            "SELECT isim, davet, plan, kayit, hayir FROM adaylar WHERE id=?",
            (aday_id,)
        ).fetchone()

        if not eski:
            return False

        isim = eski["isim"] or ""

        # DB'deki mevcut + bu olaydan gelen bayraklari OR ile birlestir
        davet_t = max(int(eski["davet"] or 0), int(davet or 0))
        plan_t  = max(int(eski["plan"]  or 0), int(plan  or 0))
        kayit_t = max(int(eski["kayit"] or 0), int(kayit or 0))
        hayir_t = max(int(eski["hayir"] or 0), int(hayir or 0))

        # v11c: Mevcut statuyu erken oku (davet kurali kosullandirma icin)
        _profil_erken = c.execute(
            "SELECT durum FROM aday_profil WHERE isim=? LIMIT 1",
            (isim,)
        ).fetchone()
        _mevcut_durum = (_profil_erken["durum"] or "") if _profil_erken else ""

        yeni_durum = None
        hedef_blok = 0
        if hayir_t == 1:
            # v11: NET hayir -> Blok, yumusak hayir -> DeepFreeze
            if int(net_hayir or 0) == 1:
                yeni_durum = _statu_adi("blok")
                hedef_blok = 1
            else:
                yeni_durum = _statu_adi("deepfreeze")
        elif plan_t == 1 and kayit_t == 1:
            yeni_durum = _statu_adi("sg")
        elif plan_t == 1 and kayit_t == 0:
            yeni_durum = _statu_adi("takip")
        elif plan_t == 0 and davet_t == 1:
            # v11c: Sadece "Değerlendirilecek" -> Aktif. Diger statuler korunur.
            _md_lower = _mevcut_durum.lower()
            if ("değerlendirilecek" in _md_lower or
                "degerlendirilecek" in _md_lower or
                not _mevcut_durum.strip()):
                yeni_durum = _statu_adi("aktif")
            else:
                return False  # Sıcak/Aktif zaten, degistirme
        else:
            return False  # Statu degismedi

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        profil = c.execute(
            "SELECT id, durum FROM aday_profil WHERE aday_id=? OR (aday_id IS NULL AND isim=?) ORDER BY (aday_id IS NULL), id ASC LIMIT 1",
            (aday_id, isim,)
        ).fetchone()

        # Zaten ayni statude ise bosuna yazma
        if profil and profil["durum"] == yeni_durum:
            return False

        if profil:
            c.execute(
                "UPDATE aday_profil SET durum=?, updated_at=? WHERE id=?",
                (yeni_durum, now, profil["id"])
            )
        else:
            c.execute(
                """
                INSERT INTO aday_profil
                (isim, telefon, email, adres, durum, aktif, created_at, updated_at, aday_id)
                VALUES (?, '', '', '', ?, 1, ?, ?, ?)
                """,
                (isim, yeni_durum, now, now, aday_id)
            )
        # v11: NET hayir ise blok=1 set et
        if hedef_blok == 1:
            c.execute(
                "UPDATE adaylar SET blok=1, blok_tarihi=?, blok_notu=? WHERE id=?",
                (now, "NET hayir - otomatik", aday_id)
            )

        c.commit()
        print(f"Otomatik statu: {isim} -> {yeni_durum}" + (" [BLOK]" if hedef_blok else ""))
        return True


def bloklu_adaylari_getir():
    """Bloklanmis adaylari listeler (ana listede gizli olanlar)."""
    with _conn(ADAY_DB) as c:
        rows = c.execute("""
            SELECT id, isim, tarih, blok_tarihi, blok_notu, linkedin_url
            FROM adaylar
            WHERE COALESCE(blok, 0) = 1
            ORDER BY COALESCE(blok_tarihi, '') DESC, id DESC
        """).fetchall()
        return [dict(r) for r in rows]


def aday_blok_kaldir(aday_id):
    """Blok kaydini kaldirir (blok=0). Aday ana listeye doner."""
    with _conn(ADAY_DB) as c:
        c.execute("""
            UPDATE adaylar
            SET blok=0, blok_tarihi=NULL, blok_notu=NULL
            WHERE id=?
        """, (aday_id,))
        c.commit()
        return c.total_changes > 0


def randevu_hatirlatmalari_getir():
    """v11: 4 asamali randevu bildirim motoru (READ ONLY).
    Sayfa acilisinda cagrilir, anlik hesaplar."""
    from datetime import datetime as _dt, timedelta as _td, date as _date
    from config import OLAY_TIPLERI

    # v11b: Sadece KULLANICI AKSIYONLARI kapanis sayilir.
    # Not/Davet/Aday Kaydi/Excel Gecmisi SAYILMAZ.
    _kapanis_kodlar = ("plan", "kayit", "hayir", "takip_g", "sadece_durum")
    KAPANIS_TIPLERI = tuple(
        t["html_value"] for t in OLAY_TIPLERI if t["kod"] in _kapanis_kodlar
    )

    def _tarih_parse(s):
        if not s:
            return None
        s = str(s).strip()
        if not s:
            return None
        # v19 Randevu Tarih Fix: Eger saat bilgisi varsa sadece tarih kismini al
        if ' ' in s or 'T' in s:
            s = s.split(' ')[0].split('T')[0]
        # v18 Tarih Kalkani (5+ haneli hatali yillari duzelt)
        import re
        if re.match(r'^\d{5,}-\d{2}-\d{2}$', s):
            s = s[-10:]
        elif re.match(r'^\d{2}/\d{2}/\d{5,}$', s):
            p = s.split('/')
            s = f"{p[0]}/{p[1]}/{p[2][-4:]}"
        elif re.match(r'^\d{2}\.\d{2}\.\d{5,}$', s):
            p = s.split('.')
            s = f"{p[0]}.{p[1]}.{p[2][-4:]}"
        for f in ("%Y-%m-%d", "%d %m %y", "%d.%m.%Y", "%d.%m.%y",
                  "%d/%m/%Y", "%d/%m/%y", "%d %m %Y", "%Y/%m/%d"):
            try:
                return _dt.strptime(s, f).date()
            except ValueError:
                continue
        return None

    bugun = _date.today()
    yarin = bugun + _td(days=1)

    sonuc = []

    with _conn(ADAY_DB) as c:
        adaylar = c.execute("""
            SELECT id, isim, randevu_tarihi, randevu_saati, takvime_eklendi
            FROM adaylar
            WHERE COALESCE(blok,0)=0
              AND COALESCE(hayir,0)=0
              AND randevu_tarihi IS NOT NULL
              AND TRIM(randevu_tarihi) <> ''
            ORDER BY randevu_tarihi, randevu_saati
        """).fetchall()

        for a in adaylar:
            r_tarih = _tarih_parse(a["randevu_tarihi"])
            if r_tarih is None:
                continue

            r_saat = (a["randevu_saati"] or "").strip()
            isim = (a["isim"] or "?").strip()

            # v11b: Kayit kontrolu — sadece randevu tarihinden
            # SONRAKI gunlerde + sadece KAPANIS tipi olaylar.
            # Ayni gun olaylar ve otomatik olaylar kapanis SAYILMAZ.
            kayit_girildi = False
            olaylar = c.execute("""
                SELECT tarih, olay_tipi FROM aday_olaylari
                WHERE kaynak_kayit_id = ?
            """, (a["id"],)).fetchall()
            for o in olaylar:
                o_t = _tarih_parse(o["tarih"])
                o_tip = (o["olay_tipi"] or "").strip()
                if o_t and o_t > r_tarih and o_tip in KAPANIS_TIPLERI:
                    kayit_girildi = True
                    break

            if kayit_girildi:
                continue

            # Asama belirle
            if r_tarih > yarin:
                asama, ikon = 1, "\U0001F4C5"
                metin = f"{isim} ile {r_tarih.strftime('%d.%m.%Y')}"
                if r_saat:
                    metin += f" saat {r_saat}"
                metin += " randevu yapildi"
            elif r_tarih == yarin:
                asama, ikon = 2, "\u23F0"
                metin = f"Yarin {isim} ile {r_tarih.strftime('%d.%m.%Y')}"
                if r_saat:
                    metin += f" saat {r_saat}"
                metin += " randevu var"
            elif r_tarih == bugun:
                asama, ikon = 3, "\U0001F514"
                metin = f"Bugun {isim} ile {r_tarih.strftime('%d.%m.%Y')}"
                if r_saat:
                    metin += f" saat {r_saat}"
                metin += " randevu var"
            else:
                asama, ikon = 4, "\u2757"
                gecikme = (bugun - r_tarih).days
                metin = f"{isim} randevu durumunu kaydedin"
                if gecikme > 1:
                    metin += f" ({gecikme} gun gecikti)"

            sonuc.append({
                "aday_id": a["id"],
                "isim": isim,
                "asama": asama,
                "ikon": ikon,
                "metin": metin,
                "tarih": r_tarih.strftime("%d.%m.%Y"),
                "saat": r_saat,
                "takvime_eklendi": a["takvime_eklendi"] if "takvime_eklendi" in a.keys() else 0,
            })

    sonuc.sort(key=lambda h: (-h["asama"], h["tarih"]))
    return sonuc


# ─── v12f: Akilli tarih parser ───
def tarih_parse(s):
    """Esnek tarih parser. Farkli formatlari sirayla dener.
    ISO (2026-10-12), TR (30.09.2026), TR-kisa (11 10 26), vs.
    Yanlis format'tan kaynakli hatalari engeller.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        import pandas as pd
    except ImportError:
        return None
    # 1. ISO format (yil-ay-gun): 2026-10-12
    try:
        return pd.to_datetime(s, format="%Y-%m-%d")
    except Exception:
        pass
    # 2. TR noktali (gun.ay.yil): 30.09.2026
    try:
        return pd.to_datetime(s, format="%d.%m.%Y")
    except Exception:
        pass
    # 3. TR kisa bosluklu (gun ay yil-2hane): 11 10 26
    try:
        return pd.to_datetime(s, format="%d %m %y")
    except Exception:
        pass
    # 4. TR kisa noktali: 11.10.26
    try:
        return pd.to_datetime(s, format="%d.%m.%y")
    except Exception:
        pass
    # 5. ISO tam (saatli): 2026-10-12 15:30:00
    try:
        return pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    # 6. Son care: dayfirst ile esnek
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce")
    except Exception:
        return None



# ============================================================
# v17 D33: Akilli Hatirlatma ve Son Gelismeler Motoru
# ============================================================
def akilli_hatirlatmalar_getir():
    """Randevulara ek olarak notlardaki anahtar kelimeleri tarar."""
    sonuc = []
    try:
        randevular = randevu_hatirlatmalari_getir()
        if randevular:
            sonuc.extend(randevular)
    except Exception as e:
        print(f"Randevu hatirlatma hatasi: {e}")

    try:
        with _conn(ADAY_DB) as c:
            c.row_factory = sqlite3.Row
            # Son 7 gundeki "kabul", "goruselim" vb. iceren olaylar
            kw_query = """
            SELECT o.id, o.kaynak_kayit_id as aday_id, a.isim, o.olay_metni, o.olay_tipi, o.tarih 
            FROM aday_olaylari o
            JOIN adaylar a ON o.kaynak_kayit_id = a.id
            WHERE o.tarih >= date('now', '-7 days')
            AND (
                lower(o.olay_metni) LIKE '%kabul%' OR
                lower(o.olay_metni) LIKE '%görüşelim%' OR
                lower(o.olay_metni) LIKE '%goruselim%' OR
                lower(o.olay_metni) LIKE '%haberleşelim%' OR
                lower(o.olay_metni) LIKE '%haberleselim%' OR
                lower(o.olay_metni) LIKE '%müsaitim%' OR
                lower(o.olay_metni) LIKE '%musaitim%'
            )
            ORDER BY o.id DESC LIMIT 10
            """
            rows = c.execute(kw_query).fetchall()
            for r in rows:
                metin = r['olay_metni'].lower()
                ikon = "💬"
                aksiyon = "Yanıt ver"
                if "kabul" in metin:
                    ikon = "🤝"
                    aksiyon = "Tanışma mesajı gönder"
                
                sonuc.append({
                    "aday_id": r['aday_id'],
                    "isim": r['isim'],
                    "asama": "Akıllı Hatırlatma",
                    "ikon": ikon,
                    "metin": f"Notunda: '{r['olay_metni'][:40]}...' yazıyor. {aksiyon}.",
                    "tarih": r['tarih'][:10] if r['tarih'] else "",
                    "aksiyon": aksiyon
                })
    except Exception as e:
        print(f"Akilli hatirlatma hatasi: {e}")

    return sonuc

def son_gelismeler_getir():
    """Son 10 kronolojik olayi dondurur."""
    try:
        with _conn(ADAY_DB) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT o.tarih, o.olay_tipi, o.olay_metni, a.isim
                FROM aday_olaylari o
                JOIN adaylar a ON o.kaynak_kayit_id = a.id
                ORDER BY o.id DESC LIMIT 10
            """).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"Son gelismeler hatasi: {e}")
        return []

# v19 Eski Aday ID Temizlendi

# v19 Randevu Tarih Fix

# v19 Aday Ekleme Son Fix

# v19 Aday Ekleme Nihai Fix
