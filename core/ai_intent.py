# -*- coding: utf-8 -*-
import json
import urllib.request
import re

# Ollama'nin yerel adresi (Eger farkli bir porttaysa config.py'den cekilebilir, varsayilan 11434)
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

def analiz_et(isim, olay_tipi, olay_metni, mevcut_durum):
    """
    Gelişmeyi analiz eder ve öneri döner.
    """
    prompt = f"""Sen bir Network Marketing uzmanısın. Adayın adı: {isim}.
Mevcut durumu: {mevcut_durum}
Olay Tipi: {olay_tipi}
Not/Mesaj: "{olay_metni}"

Bu gelişmeyi analiz et. Adayla güven inşa etmek ve iş planı sunmak istiyoruz. 
Aşağıdaki kurallara göre sadece JSON çıktısı ver:
1. "niyet": (Olumlu, Olumsuz, Notr, Randevu_Talebi)
2. "onerilen_durum": (Sıcak, Aktif, Değerlendirilecek, Olumsuz, Randevu Alındı, Plan Sunuldu, Takip Ediliyor, Kayıt Yapıldı)
   - "Sıcak": Görüşmeye/randevuya açık (ör: "konuşalım", "neden olmasın")
   - "Randevu Alındı": Net bir randevu tarihi/saati verildi.
   - "Plan Sunuldu": İş planı/zoom toplantısı yapıldı.
   - "Takip Ediliyor": Ulaşılamadı veya düşünme aşamasında.
   - "Kayıt Yapıldı": Aday sisteme/ekibe katıldı.
   - "Aktif": İletişim var ama net değil
   - "Olumsuz": İlgilenmiyor, net ret.
3. "ai_not": Kısa bir açıklama ve atılacak sonraki adım. (Örn: "Görüşmeye açık, hemen Zoom randevusu isteyin.")

ÇIKTI SADECE JSON OLMALIDIR, başka bir metin yazma:
{{
  "niyet": "...",
  "onerilen_durum": "...",
  "ai_not": "..."
}}
"""
    
    # API istegi hazirligi
    data = {
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL, 
            data=json.dumps(data).encode("utf-8"), 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            yanit = result.get("response", "")
            
            # JSON temizligi
            yanit = yanit.replace("```json", "").replace("```", "").strip()
            return json.loads(yanit)
            
    except Exception as e:
        print(f"[AI INTENT] Hata: {e}")
        return None
