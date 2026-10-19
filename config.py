from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Veritabanlari
ADAY_DB = DATA_DIR / "linkedin_takip.db"
CHAT_DB = DATA_DIR / "sohbet_gecmisi.db"

# Izlenen Excel dosyasi (watcher bunu izler)
IZLENEN_EXCEL = DATA_DIR / "izlenen_adaylar.xlsx"

# Ollama ayarlari
OLLAMA_HOST = "http://127.0.0.1:11434"

# MODEL AYARLARI â€” Intel Arc 140V (16 GB VRAM) iÃ§in optimize

# --- Aktif Modeller ---
# Ana sohbet modeli (kalite odaklÄ±)
DEFAULT_MODEL = "qwen2.5:14b"  # trendyol-7b yerine

# Model Ã§Ã¶kerse veya bulunamazsa devreye girer
DEFAULT_FALLBACK = "qwen2.5:7b"  

# ArayÃ¼z dropdown'Ä±nda gÃ¶sterilecek modeller (sÄ±ralÄ±)
PRIMARY_MODELS = [
    "qwen2.5:14b",       # yÃ¼ksek kalite
    "qwen2.5:7b",        # dengeli (hÄ±zlÄ±)
    "qwen2.5:3b",        # Ã§ok hÄ±zlÄ± (basit sorular)
    "llama3.1:latest",   # alternatif
]

# Fallback zinciri (sÄ±rayla denenir)
FALLBACK_MODELS = [
    "qwen2.5:7b",
    "qwen2.5:3b",
]

# --- Model BaÅŸÄ±na Context (num_ctx) ---
# Daha bÃ¼yÃ¼k context = daha fazla KV cache = daha yavaÅŸ
MODEL_CONTEXT_MAP = {
    "qwen2.5:14b": 12288,   # v13 - JSON icin optimize
    "qwen2.5:7b": 8192,     # v17 D36: 7B Context Optimizasyonu
    "qwen2.5:3b": 4096,        # 3B için 4096 yeterli
    "llama3.1:latest": 8192,
}


# --- Model Basina Num Predict (maksimum cikti token) ---
# v16 (manifest 11.1): yanit suresini kontrol icin cikti limiti.
# -1 = sinirsiz, -2 = context doluncaya kadar, pozitif = limit
MODEL_NUM_PREDICT_MAP = {
    "qwen2.5:14b": 1024,       # ozet/strateji - derin analiz
    "qwen2.5:7b": 1024,        # chat - hizli yanit
    "qwen2.5:3b": 1024,
    "llama3.1:latest": 2048,
}

# --- Model BaÅŸÄ±na Temperature ---
# DÃ¼ÅŸÃ¼k = tutarlÄ±, YÃ¼ksek = yaratÄ±cÄ±
MODEL_TEMP_MAP = {
    "qwen2.5:14b": 0.35,       # ana model — tutarlı/kaliteli
    "qwen2.5:7b": 0.45,        # fallback
    "qwen2.5:3b": 0.40,        # hızlı işler
    "llama3.1:latest": 0.50,   # alternatif
}

# --- Genel Sabitler ---
DEFAULT_NUM_CTX = 12288
NUM_CTX = DEFAULT_NUM_CTX

# Modelin VRAM'de kalma sÃ¼resi (24h = sÃ¼rekli hazÄ±r, reload yok)
KEEP_ALIVE = "24h"

# --- Aday OlaylarÄ± (context iÃ§in) ---
ADAY_OLAY_LIMIT = 3
ADAY_PROMPT_LIMIT = 20
CHAT_MODEL = "qwen2.5:7b"  # v15: chat icin hafif model (7B)


# ═══════════════════════════════════════════════════════════════════════
# v6 MADDE 4 — AI PARAMETRELERI + STATU/OLAY TEK KAYNAK
# ═══════════════════════════════════════════════════════════════════════

# --- Model Basina Top-p (nucleus sampling) ---
MODEL_TOP_P_MAP = {
    "qwen2.5:14b": 0.90,
    "qwen2.5:7b": 0.90,
    "qwen2.5:3b": 0.95,
    "llama3.1:latest": 0.90,
}

# --- Model Basina Top-k ---
MODEL_TOP_K_MAP = {
    "qwen2.5:14b": 40,
    "qwen2.5:7b": 40,
    "qwen2.5:3b": 50,
    "llama3.1:latest": 40,
}

# --- Model Basina Repeat Penalty ---
MODEL_REPEAT_PENALTY_MAP = {
    "qwen2.5:14b": 1.15,
    "qwen2.5:7b": 1.15,
    "qwen2.5:3b": 1.10,
    "llama3.1:latest": 1.10,
}

# --- Model Basina Repeat Last N ---
MODEL_REPEAT_LAST_N_MAP = {
    "qwen2.5:14b": 256,
    "qwen2.5:7b": 256,
    "qwen2.5:3b": 256,
    "llama3.1:latest": 256,
}

# --- Analiz Profili (strateji/degerlendirme istekleri icin dusuk temp) ---
ANALIZ_TEMP_MAP = {
    "qwen2.5:14b": 0.20,
    "qwen2.5:7b": 0.25,
    "qwen2.5:3b": 0.30,
    "llama3.1:latest": 0.25,
}

# --- Sohbet Baglami ---
CHAT_GECMIS_LIMIT = 6

# --- ADAY STATULERI (TEK KAYNAK) ---
# DB'de ve UI dropdown'larinda bu "tam" deger kullanilir.
ADAY_STATULERI = [
    # ON TESPIT (aday listeye girerken kullanici secer)
    {"kod": "degerlendirilecek", "tam": "⚪ Değerlendirilecek", "katman": "on_tespit",
     "aciklama": "Sonra degerlendirilmek uzere"},
    {"kod": "aktif", "tam": "🟢 Aktif", "katman": "on_tespit",
     "aciklama": "Surec devam ediyor"},
    {"kod": "sicak", "tam": "🔥 Sıcak", "katman": "on_tespit",
     "aciklama": "Yuksek potansiyel, acil takip"},
    # SONUC (surec sonunda atanir)
    {"kod": "takip", "tam": "🔔 Takip", "katman": "sonuc",
     "aciklama": "Plan OK, kayit yok"},
    {"kod": "sg", "tam": "🎓 SG", "katman": "sonuc",
     "aciklama": "Kayit tamamlandi"},
    {"kod": "deepfreeze", "tam": "❄️ DeepFreeze", "katman": "sonuc",
     "aciklama": "Yumusak hayir"},
    {"kod": "blok", "tam": "⛔ Blok", "katman": "sonuc",
     "aciklama": "Net hayir, listeden gizli"},
]

# --- OLAY TIPLERI (TEK KAYNAK — bugun duzeltilen bug icin) ---
# UI dropdown'inda gorunen "tam" deger ile eslesir.
# "bayrak" alani: bu olay secildiginde hangi checkbox set edilir.
OLAY_TIPLERI = [
    {"kod": "not",          "html_value": "Not",                "bayrak": None},
    {"kod": "davet",        "html_value": "Davet",              "bayrak": "davet"},
    {"kod": "plan",         "html_value": "Plan",               "bayrak": "plan"},
    {"kod": "takip_g",      "html_value": "Takip Görüşmesi",    "bayrak": "takip"},
    {"kod": "kayit",        "html_value": "Kayıt",              "bayrak": "kayit"},
    {"kod": "hayir",        "html_value": "Hayır",              "bayrak": "hayir"},
    {"kod": "sadece_durum", "html_value": "Durum Değişikliği",  "bayrak": None},
]

# --- Statu Gecis Kurallari (Otomatik) ---
# v11: NET hayir -> blok, yumusak hayir -> deepfreeze
# hayir=1 + net_hayir=1 -> blok
# hayir=1 + net_hayir=0 -> deepfreeze
STATU_GECIS_KURALLARI = [
    {"kosul": "net_hayir=1",        "hedef": "blok",       "tip": "otomatik"},
    {"kosul": "hayir=1",            "hedef": "deepfreeze", "tip": "otomatik"},
    {"kosul": "plan=1 and kayit=1", "hedef": "sg",         "tip": "otomatik"},
    {"kosul": "plan=1 and kayit=0", "hedef": "takip",      "tip": "otomatik"},
    {"kosul": "plan=0 and davet=1", "hedef": "aktif",      "tip": "otomatik"},
]
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5050
FLASK_DEBUG = False