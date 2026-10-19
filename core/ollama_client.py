import ollama
import time
from datetime import datetime
import psutil


from config import (MODEL_CONTEXT_MAP, MODEL_TEMP_MAP, DEFAULT_NUM_CTX,
                    KEEP_ALIVE, DEFAULT_MODEL, DEFAULT_FALLBACK,
                    MODEL_TOP_P_MAP, MODEL_TOP_K_MAP,
                    MODEL_REPEAT_PENALTY_MAP, MODEL_REPEAT_LAST_N_MAP,
                    ADAY_STATULERI, ANALIZ_TEMP_MAP)

# v16: num_predict - cikti limiti (manifest 11.1)
from config import MODEL_NUM_PREDICT_MAP
_warmed_models = set()

def _get_num_ctx(model_adi):
    """Model bazli akilli num_ctx dondurur."""
    return MODEL_CONTEXT_MAP.get(model_adi, DEFAULT_NUM_CTX)

def _get_temp(model_adi, profil=None):
    """Model bazli temperature dondurur.

    profil="analiz" ise ANALIZ_TEMP_MAP (dusuk temp: tutarli analiz),
    aksi halde MODEL_TEMP_MAP kullanilir.
    """
    if profil == "analiz":
        return ANALIZ_TEMP_MAP.get(model_adi, MODEL_TEMP_MAP.get(model_adi, 0.5))
    return MODEL_TEMP_MAP.get(model_adi, 0.5)

def _get_top_p(model_adi):
    """Model bazli top_p dondurur."""
    return MODEL_TOP_P_MAP.get(model_adi, 0.9)

def _get_top_k(model_adi):
    """Model bazli top_k dondurur."""
    return MODEL_TOP_K_MAP.get(model_adi, 40)

def _get_repeat_penalty(model_adi):
    """Model bazli repeat_penalty dondurur."""
    return MODEL_REPEAT_PENALTY_MAP.get(model_adi, 1.15)

def _get_repeat_last_n(model_adi):
    """Model bazli repeat_last_n dondurur."""
    return MODEL_REPEAT_LAST_N_MAP.get(model_adi, 256)

def _get_num_predict(model_adi):
    """Model bazli num_predict (max cikti token) dondurur.

    v16 (manifest 11.1): yanit suresini kontrol icin cikti limiti.
    -1 = sinirsiz, -2 = context doluncaya kadar, pozitif = token limiti.
    """
    return MODEL_NUM_PREDICT_MAP.get(model_adi, 2048)

def warm_up(model_adi=DEFAULT_MODEL):
    """Modeli VRAM e yukler. Uygulama acilisinda bir kere cagrilir."""
    if model_adi in _warmed_models:
        return True
    try:
        num_ctx = _get_num_ctx(model_adi)
        print(f"Warm-up: {model_adi} (num_ctx: {num_ctx})")
        ollama.generate(
            model=model_adi,
            prompt="",
            options={"num_ctx": num_ctx, "num_predict": 0},
            keep_alive=KEEP_ALIVE
        )
        _warmed_models.add(model_adi)
        print(f"OK: {model_adi} VRAM e yuklendi")
        return True
    except Exception as e:
        print(f"UYARI: Warm-up hatasi ({model_adi}): {e}")
        return False

def _statuleri_metne_cevir():
    """config.ADAY_STATULERI'ndan sistem promptu icin statu listesi uretir."""
    on_tespit = [s for s in ADAY_STATULERI if s.get("katman") == "on_tespit"]
    sonuc = [s for s in ADAY_STATULERI if s.get("katman") == "sonuc"]

    satirlar = ["STARTING STATUSES (user selects when creating a candidate):"]
    for i, s in enumerate(on_tespit, 1):
        satirlar.append(f"{i}. {s['tam']}: {s['aciklama']}")
    satirlar.append("")
    satirlar.append("AUTOMATIC STATUSES (system assigns based on events):")
    for i, s in enumerate(sonuc, len(on_tespit) + 1):
        satirlar.append(f"{i}. {s['tam']}: {s['aciklama']}")
    return "\n".join(satirlar)


def _sistem_prompt(df_ozet):
    statu_metni = _statuleri_metne_cevir()
    return f"""[SYSTEM ROLE & CORE OBJECTIVE]
You are an elite, highly rigorous AI Executive Assistant and Chief Data Analyst specialized in Candidate Tracking Systems (ATS), Network Marketing operations, conversion forecasting, and behavioral pattern analysis.
Your core objective is to act as a strategic partner: analyzing candidate progression, predicting conversion probabilities based on historical patterns, identifying bottlenecks, and providing actionable, forward-looking recommendations.

[CANDIDATE CATEGORIES (The EXACT statuses in this system)]
{statu_metni}

[STATUS TRANSITION RULES]
- Plan ✓ + Kayıt ✓ → 🎓 SG (Mezun)
- Plan ✓ + Kayıt ✗ → 🔔 Takip
- Davet ✓ + Plan ✗ → 🟢 Aktif (sadece Değerlendirilecek'ten)
- NET HAYIR (aday reddetti, net hayır, asla) → ⛔ Blok (otomatik)
- YUMUŞAK HAYIR (olumsuz yanıt, henüz evet demedi) → ❄️ DeepFreeze (otomatik)

Kullanıcı her zaman manuel statü değiştirebilir.

[IMPORTANT]
- The ONLY valid starting statuses are: ⚪ Değerlendirilecek, 🟢 Aktif, or 🔥 Sıcak.
- Use ONLY the statuses explicitly listed in the CANDIDATE DATA section above.

[ANTI-HALLUCINATION RULES (CRITICAL - v17 B3: Anti-Hallucination Shield)]
- **STRICT DATA BOUNDARY:** You are ONLY allowed to use the candidate names, numbers, and data explicitly provided in the [CANDIDATE DATA] section below.
- **NEVER INVENT DATA:** Do NOT invent candidate names, phone numbers, or statistics. If a candidate is not in the provided list, they do not exist.
- **NO MENTAL MATH:** Do NOT calculate totals or perform mental math unless the exact numbers are provided in the statistics section. If the user asks for a total, read the provided total.
- **CONTEXT LIMIT AWARENESS:** If the user asks for "more" candidates and you have reached the end of the provided list, state EXACTLY: "Sistemde şu an sadece bu kadar aday görünüyor veya tarama limitine ulaşıldı. Daha fazlası için filtreleri daraltın." Do NOT create fake names to satisfy the request.

[ANTI-HALLUCINATION RULES (CRITICAL - v17 B3: Anti-Hallucination Shield)]
- **STRICT DATA BOUNDARY:** You are ONLY allowed to use the candidate names, numbers, and data explicitly provided in the [CANDIDATE DATA] section below.
- **NEVER INVENT DATA:** Do NOT invent candidate names, phone numbers, or statistics. If a candidate is not in the provided list, they do not exist.
- **NO MENTAL MATH:** Do NOT calculate totals or perform mental math unless the exact numbers are provided in the statistics section. If the user asks for a total, read the provided total.
- **CONTEXT LIMIT AWARENESS:** If the user asks for "more" candidates and you have reached the end of the provided list, state EXACTLY: "Sistemde şu an sadece bu kadar aday görünüyor veya tarama limitine ulaşıldı. Daha fazlası için filtreleri daraltın." Do NOT create fake names to satisfy the request.

[ADVANCED CAPABILITIES & TASKS]
1. Predictive Modeling & Probability: Evaluate candidate statuses (invitations, meetings, presentations, registrations) to calculate conversion likelihoods and predict dropouts.
2. Trend & Behavioral Analysis: Detect patterns in qualitative notes and timestamps to assess momentum and timing effectiveness.
3. Strategic Recommendations: Proactively suggest precise, high-impact next steps. Every recommendation MUST include: Category + Action + Reason.

[CALENDAR & PLANNING DISCIPLINE (CRITICAL)]
When the user asks for a weekly schedule or a working plan, you MUST follow these strict rules:
1. **NO SKIPPED DAYS:** List ALL 7 days sequentially: Pazartesi, Salı, Çarşamba, Perşembe, Cuma, Cumartesi, Pazar. Never skip.
2. **CHRONOLOGICAL ORDER:** Days follow each other strictly without jumping.
3. **DATE FORMAT:** Use Turkish format "gg.aa.yyyy" (e.g., 04.10.2026).
4. **NO INVENTED HOLIDAYS:** Do NOT invent holidays or skip days for "tatil". If a Turkish public holiday is known (like 29 Ekim Cumhuriyet Bayramı), mention it but still include the day in the list.
5. **TODAY'S DATE:** The current date will be provided by the user or system; use it as the starting point for "this week" / "next week" plans.
6. **START FROM TODAY (CRITICAL):** If today is NOT Monday, DO NOT start the plan from Pazartesi. Start from TODAY and list the next 7 days sequentially.
   - Example: If today is Cuma (Friday), list: Cuma, Cumartesi, Pazar, Pazartesi, Sali, Carsamba, Persembe.
   - Assign CORRECT dates to each day name. Do not mismatch day names with dates.
   - Verify: Pazartesi = Monday, Sali = Tuesday, Carsamba = Wednesday, Persembe = Thursday, Cuma = Friday, Cumartesi = Saturday, Pazar = Sunday.

[EXCEL / CSV FORMAT RULE]
When the user requests an Excel format, table, or working plan to be exported, DO NOT use Markdown pipes (|). Instead, output strict CSV format using semicolon (;) as the separator inside a ```csv code block, so the user can save it directly as a .csv file and open it in Excel.

[RESPONSE FORMAT (when recommending actions)]
Oneri: [Adayi X kategorisine cek]
Gerekce: [Kisa aciklama, veriye dayali]
Aksiyon: [Somut, tarihli öneri]

# CANDIDATE DATA
{df_ozet}

# HARD RULES (NON-NEGOTIABLE)
1. GROUNDING: Every factual claim MUST be traceable to the data above.
2. NO FABRICATION (STRICT): If a candidate's status, note, or date is NOT explicitly provided in the CANDIDATE DATA section, you MUST state that it is missing. DO NOT invent dates, DO NOT hallucinate notes. If the data says "No contact", DO NOT invent past interactions.
3. CATEGORY PRECISION: Use ONLY the official funnel categories listed above.
4. LANGUAGE: CRITICAL - Your ENTIRE reply must be in fluent, natural, professional Turkish. Never reply in English.
5. CONCISE: No long essays. 5-10 lines maximum per answer (unless a weekly schedule is explicitly requested).
6. NO STATISTICS PADDING: If user asks a simple count, answer with the count only.
7. DATA ACCESS: The CANDIDATE DATA section above contains a SUMMARY of recent candidates and their latest events, NOT the entire database. Carefully read the provided section first. If a candidate, a history detail, or a contact info is not present in the provided text, you MUST explicitly state that you cannot see it in the current context. DO NOT invent missing history, contact details, or events.
8. OUTPUT LANGUAGE: Your entire response must be in Turkish. Every word, every list, every explanation. No exceptions.
9. NO LATEX / MARKDOWN MATH: Write numbers and arithmetic in plain text. Never use \[ \], $...$, \frac, \sum, or any LaTeX. Example: "29 + 33 + 28 + 1 + 3 = 94" (plain text)."""


def chat_stream(mesajlar, model=DEFAULT_MODEL, fallback=DEFAULT_FALLBACK, durum=None, profil=None, format=None):
    # v17 D26: Prefix Cache engelleme (Nonce)
    import datetime as _dt_nonce
    _nonce = _dt_nonce.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    mesajlar = [dict(m) for m in mesajlar]
    if mesajlar and mesajlar[0].get('role') == 'system':
        mesajlar[0]['content'] += f"\n[Session Nonce: {_nonce}]"
    else:
        mesajlar.insert(0, {'role': 'system', 'content': f"[Session Nonce: {_nonce}]"})

    """Generator: Ollama dan gelen chunk lari yield eder. Fallback li.

    profil: "analiz" -> dusuk temperature (ANALIZ_TEMP_MAP)
    """
    if durum is None:
        durum = {}
    durum["model"] = model
    durum["fallback"] = False
    durum["profil"] = profil

    def _deneme(m):
        t0 = time.time()
        num_ctx = _get_num_ctx(m)
        num_pred = _get_num_predict(m)   # v16
        sicaklik = _get_temp(m, profil)
        print(f"{m} cagriliyor (num_ctx: {num_ctx}, num_predict: {num_pred}, temp: {sicaklik})...")
        full = ollama.chat(
            model=m,
            messages=mesajlar,
            options={
                "num_ctx": num_ctx,
                "num_predict": num_pred,   # v16
                "temperature": sicaklik,
                "top_p": _get_top_p(m),
                "top_k": _get_top_k(m),
                "repeat_penalty": _get_repeat_penalty(m),
                "repeat_last_n": _get_repeat_last_n(m),
            },
            keep_alive=KEEP_ALIVE,
            stream=True,
            format=format
        )
        ilk = True
        for chunk in full:
            if ilk:
                print(f"{m} ilk token: {time.time()-t0:.1f}sn")
                ilk = False
            yield chunk["message"]["content"]

    try:
        yield from _deneme(model)
    except Exception as e:
        print(f"{model} hata verdi, fallback: {fallback} ({e})")
        durum["fallback"] = True
        durum["model"] = fallback
        yield f"\n\n*(Not: {model} yanit vermedigi icin {fallback} ile yanitlaniyor)*\n\n"
        try:
            yield from _deneme(fallback)
        except Exception as e2:
            yield f"\n\nFallback de basarisiz: {e2}"


def sistem_mesaji_olustur(df_ozet):
    """Sistem prompt'una bugunun tarihini enjekte eder."""
    bugun = datetime.now()
    
    # Turkce gun isimleri
    gunler = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
             "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
    
    gun_adi = gunler[bugun.weekday()]
    ay_adi = aylar[bugun.month - 1]
    
    tarih_bilgisi = f"""
[CURRENT DATE - TODAY]
Bugun: {bugun.strftime('%d.%m.%Y')} ({gun_adi})
Ay: {ay_adi} {bugun.year}
Yil: {bugun.year}

[CRITICAL DATE RULE]
- GECMIS tarihleri AYNEN koru (veri ne diyorsa o).
- YENI plan/randevu tarihleri icin bugunu referans al: {bugun.strftime('%d.%m.%Y')}
- "Bu hafta" = {bugun.strftime('%d.%m.%Y')} haftasi
- "Gelecek hafta" = bir sonraki hafta
- Belirsiz tarih uydurma, bos birak.
- Ornek dogru format: {bugun.strftime('%d.%m.%Y')}
"""
    
    return {"role": "system", "content": _sistem_prompt(df_ozet) + tarih_bilgisi}


def _alan(obj, ad, varsayilan=None):
    """dict veya pydantic-tarzi objeden guvenli alan okuma."""
    if obj is None:
        return varsayilan
    if hasattr(obj, "get"):
        try:
            v = obj.get(ad, varsayilan)
            if v is not None:
                return v
        except Exception:
            pass
    return getattr(obj, ad, varsayilan)


def durum_ozeti():
    """Nav daki durum pili icin: Ollama ayakta mi, hangi model VRAM de?"""
    try:
        ps = ollama.ps()
        modeller = _alan(ps, "models", []) or []
        sonuc = []
        for m in modeller:
            sonuc.append({
                "name": _alan(m, "model") or _alan(m, "name"),
                "size": _alan(m, "size"),
                "vram": _alan(m, "size_vram", 0) or 0,
                "until": str(_alan(m, "expires_at", "")) or "",
            })
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
        except Exception:
            cpu_pct = None
        return {
            "ok": True,
            "models": sonuc,
            "cpu_percent": cpu_pct,
            "gpu_aktif": len(sonuc) > 0,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "models": [], "cpu_percent": None, "gpu_aktif": False}