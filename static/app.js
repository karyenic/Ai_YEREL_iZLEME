/* ============================================================
   ADAY LİSTESİ
   ============================================================ */

let aktifAdayId = null;


function htmlGuvenli(metin) {
  const div = document.createElement("div");
  div.textContent = metin == null ? "" : String(metin);
  return div.innerHTML;
}


async function adaylariYukle() {

  const r = await fetch("/api/candidates");
  const adaylar = await r.json();

  const tbody = document.querySelector("#aday-tablo tbody");

  if (!tbody) return;

  tbody.innerHTML = "";

  const urlParams = new URLSearchParams(window.location.search);
  const metrikFiltresi = urlParams.get("metrik");

  const goruntulenecekAdaylar =
    metrikFiltresi &&
    metrikFiltresi !== "toplam" &&
    metrikFiltresi !== ""
      ? adaylar.filter(
          a => Number(a[metrikFiltresi] || 0) === 1
        )
      : adaylar;
  let siraNo = 0;
  for (const a of goruntulenecekAdaylar) {
    siraNo++;

    const tr = document.createElement("tr");
    tr.className = "aday-satir";
    tr.dataset.adayId = String(a.id);

    const bool = v =>
      v == 1
        ? '<span class="yes">✓</span>'
        : '<span class="no">✗</span>';

    tr.innerHTML = `
      <td>${siraNo}</td>

            <td>
        ${a.linkedin_url 
          ? `<a href="${htmlGuvenli(a.linkedin_url)}" 
                target="_blank" 
                onclick="event.stopPropagation();"
                class="isim-link"
                title="LinkedIn profilini aç">${htmlGuvenli(a.isim)}</a>`
          : `<strong>${htmlGuvenli(a.isim)}</strong>`}
      </td>

      <td>${htmlGuvenli(a.tarih || "")}</td>

      <td title="${htmlGuvenli(aciklamaTemizle(a.aciklama))}">
        <span class="durum-top" title="${htmlGuvenli(durumEtiketi(a.durum))}">${durumTopp(a.durum)}</span>${htmlGuvenli(aciklamaTemizle(a.aciklama).slice(0, 60))}
      </td>

      <td style="white-space:nowrap; text-align:right;">
        <button
          onclick="event.stopPropagation(); adaySilOnay(${a.id}, '${htmlGuvenli(a.isim).replace(/'/g, "\\'")}')"
          style="background:#da3633;padding:7px 11px;font-size:13px;"
          title="Adayı Sil"
        >
          🗑️ Sil
        </button>
      </td>
    `;

    tr.addEventListener("click", (e) => {
      if (e.target.closest("a") || e.target.closest("button")) {
        return;
      }
      adayKartiAc(Number(tr.dataset.adayId));
    });

    tbody.appendChild(tr);
  }

  tbody.querySelectorAll(".btn-sil").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      adaySilOnay(
        Number(btn.dataset.adayId),
        btn.dataset.adayIsim || ""
      );
    });
  });
}


async function adayEkle() {

  const d = {
    isim: document.getElementById("isim").value,
    tarih: (function() {
      const d = new Date();
      return String(d.getDate()).padStart(2, "0") + " " +
             String(d.getMonth() + 1).padStart(2, "0") + " " +
             String(d.getFullYear()).slice(-2);
    })(),
    aciklama: document.getElementById("aciklama").value,

    davet: 0,
    randevu: 0,
    plan: 0,
    kayit: 0,
    takip: 0,
    hayir: 0,
    is_ariyor: 0,
    durum: document.getElementById("yeni-aday-durum") ? document.getElementById("yeni-aday-durum").value : "⚪ Değerlendirilecek",
    linkedin_url: (document.getElementById("linkedin-url")?.value || "").trim() || null,
  };

  if (!d.isim.trim()) {
    alert("İsim zorunlu");
    return;
  }

  const r = await fetch(
    "/api/candidates",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(d)
    }
  );

  const sonuc = await r.json();

  if (!sonuc.ok) {
    alert(sonuc.error || "Aday eklenemedi.");
    return;
  }

  document.getElementById("isim").value = "";
  document.getElementById("aciklama").value = "";

  adaylariYukle();
}


/* ============================================================
   ADAY KARTI
   ============================================================ */

async function adayKartiAc(adayId) {

  aktifAdayId = adayId;

  const modal = document.getElementById("aday-modal");

  if (!modal) return;

  modal.classList.remove("hidden");

  document.body.style.overflow = "hidden";

  document.getElementById("kart-isim").textContent = "Yükleniyor...";
  document.getElementById("aday-gecmis").innerHTML =
    '<div class="gecmis-bos">⏳ Aday bilgileri okunuyor...</div>';

  try {

    const r = await fetch(
      `/api/candidates/${adayId}`
    );

    const sonuc = await r.json();

    if (!r.ok || !sonuc.ok) {
      throw new Error(
        sonuc.error || "Aday bilgileri alınamadı."
      );
    }

    adayKartiDoldur(sonuc.data);

  } catch (e) {

    document.getElementById("kart-isim").textContent =
      "Hata";

    document.getElementById("aday-gecmis").innerHTML =
      `<div class="gecmis-bos">❌ ${htmlGuvenli(e.message)}</div>`;
  }
}



// v18.39: Statu Kodlarini Gorsel Metne Ceviren Fonksiyon
function formatStatu(kod) {
    if (!kod) return { ikon: "⚪", metin: "Değerlendirilecek", sinif: "" };
    
    // Tüm emojileri ve harf dışı karakterleri sil, Türkçe karakterleri İngilizceye çevir
    let k = String(kod).toLowerCase()
        .replace(/ı/g, "i")
        .replace(/İ/g, "i")
        .replace(/ğ/g, "g")
        .replace(/ü/g, "u")
        .replace(/ş/g, "s")
        .replace(/ö/g, "o")
        .replace(/ç/g, "c")
        .replace(/[^a-z0-9]/g, ""); 
    
    if (k.includes("sicak")) return { ikon: "🔥", metin: "Sıcak", sinif: "durum-sicak" };
    if (k.includes("aktif")) return { ikon: "🟢", metin: "Aktif", sinif: "" };
    if (k.includes("deepfreeze")) return { ikon: "❄️", metin: "DeepFreeze", sinif: "durum-deepfreeze" };
    if (k.includes("blok") || k.includes("olumsuz")) return { ikon: "🚫", metin: "Bloklu", sinif: "durum-blok" };
    if (k.includes("sg") || k.includes("kayityapildi")) return { ikon: "🤝", metin: "Kayıt Yapıldı", sinif: "durum-sg" };
    if (k.includes("takip")) return { ikon: "🔔", metin: "Takip Ediliyor", sinif: "durum-takip" }; // v18 Status Sync Fix
    if (k.includes("plan")) return { ikon: "📋", metin: "Plan Sunuldu", sinif: "durum-plan" };
    
    // Değerlendirilecek veya bilinmeyen her şey için NEW (⚪) DEĞİL, nötr (⚪) kullan
    return { ikon: "⚪", metin: "Değerlendirilecek", sinif: "" };
}

function adayKartiDoldur(data) {
  // v19 AI Panel Baslangic
  let aiPanel = document.getElementById("kart-ai-oneri");
  if (!aiPanel) {
      aiPanel = document.createElement("div");
      aiPanel.id = "kart-ai-oneri";
      aiPanel.style.cssText = "margin-top: 10px; padding: 10px; background: rgba(137, 87, 229, 0.1); border: 1px solid #8957e5; border-radius: 6px; font-size: 14px; color: #c9d1d9; display: none;";
      const isimEl = document.getElementById("kart-isim");
      if (isimEl && isimEl.parentNode) {
          isimEl.parentNode.insertBefore(aiPanel, isimEl.nextSibling);
      }
  }
  
  if (data.ai_oneri_durum) {
      aiPanel.innerHTML = `🤖 <strong style="color:#a371f7;">AI Önerisi:</strong> ${data.ai_oneri_durum}<br><span style="color:#8b949e; font-size:13px;">${data.ai_oneri_not || ""}</span>
      <button onclick="aiOneriOnayla(${data.id}, '${data.ai_oneri_durum}')" style="margin-left:10px; background:#8957e5; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:12px;">Onayla</button>`;
      aiPanel.style.display = "block";
  } else {
      aiPanel.style.display = "none";
  }
  // v19 AI Panel Bitis


  document.getElementById("kart-isim").textContent =
    data.isim || "Aday";

  linkedinLinkGuncelle(data.linkedin_url || "");
      document.getElementById("kart-telefon").value =
    data.telefon || "";

  document.getElementById("kart-email").value =
    data.email || "";

  document.getElementById("kart-adres").value =
    data.adres || "";

  // v18.47: Kart Durumunu Cevirici ile Guncelle ve Title'i temizle
  const sObj = formatStatu(data.durum);
  const badgeEl = document.getElementById("kart-durum");
  if (badgeEl) {
      badgeEl.textContent = `${sObj.ikon} ${sObj.metin}`;
      badgeEl.className = `durum-badge ${sObj.sinif}`;
      badgeEl.title = sObj.metin; // Fareyle uzerine gelince sadece temiz metin gorunsun
  }

  // v18.20: Kusursuz Header Hizalama
  const isimEl = document.getElementById("kart-isim");
  const durumEl = document.getElementById("kart-durum");
  const headerContainer = isimEl.closest('.aday-modal-header') || isimEl.parentElement;

  // Eger daha once yapilmadiysa ana satiri olustur
  if (headerContainer && !document.getElementById("header-flex-wrapper")) {
      // Eski bosluklari temizle
      const eskiWrap = headerContainer.querySelector('.isim-durum-wrap');
      if (eskiWrap) eskiWrap.remove();

      // Yeni Esnek Kapsayici
      const wrapper = document.createElement("div");
      wrapper.id = "header-flex-wrapper";
      wrapper.style.cssText = "display:flex; justify-content:space-between; align-items:center; width:100%; margin-top:10px; flex-wrap:wrap; gap:10px;";

      // Sol Taraf (Durum + Isim)
      const leftDiv = document.createElement("div");
      leftDiv.style.cssText = "display:flex; align-items:center; gap:12px;";
      leftDiv.appendChild(durumEl); // Rozet solda
      leftDiv.appendChild(isimEl);  // Isim sagda

      wrapper.appendChild(leftDiv);
      
      // Randevu Kutusunu (infoDiv) sag tarafa ekle
      const infoDiv = document.getElementById("kart-randevu-info");
      if (infoDiv) {
          wrapper.appendChild(infoDiv);
      }

      // Kapsayiciyi header'a ekle
      headerContainer.appendChild(wrapper);
      
      // Stil sifirlamalari
      isimEl.style.margin = "0";
      durumEl.style.margin = "0";
  }

  adayGecmisiGoster(data.gecmis || []);

  // v17 Randevu Input Doldur
  const rTarih = data.randevu_tarihi || "";
  const rSaat = data.randevu_saati || "";
  const inpTarih = document.getElementById("gelisme-randevu-tarihi");
  const inpSaat = document.getElementById("gelisme-randevu-saati");
  if (inpTarih) inpTarih.value = rTarih;
  if (inpSaat) inpSaat.value = rSaat;

  let infoDiv = document.getElementById("kart-randevu-info");
  if (!infoDiv) {
      infoDiv = document.createElement("div");
      infoDiv.id = "kart-randevu-info";
      infoDiv.style.cssText = "margin-top: 10px; padding: 8px; background: rgba(56, 139, 253, 0.1); border: 1px solid #388bfd; border-radius: 6px; font-size: 14px; color: #58a6ff; display: none;";
      const mainRow = document.getElementById("kart-header-main-row");
      if (mainRow && infoDiv.parentElement !== mainRow) {
          // infoDiv'i ana satira (saga) ekle
          mainRow.appendChild(infoDiv);
      } else if (!mainRow) {
          // Eger ana satir yoksa eski yontemle devam et
          const isimEl = document.getElementById("kart-isim");
          if (isimEl && isimEl.parentNode) {
              isimEl.parentNode.insertBefore(infoDiv, isimEl.nextSibling);
          }
      }
  }

  if (rTarih || rSaat) {
      let tBtn = "";
      if (rTarih) {
          let raw_t = rTarih; let raw_s = rSaat || "09:00";
          let g_t = raw_t.includes('.') ? raw_t.split('.').reverse().join('') : raw_t.replace(/-/g, '');
          let u_h = parseInt(raw_s.split(':')[0]) - 3; if (u_h < 0) u_h += 24;
          let u_m = raw_s.split(':')[1] || '00';
          let startStr = `${g_t}T${String(u_h).padStart(2,'0')}${u_m}00Z`;
          let endStr = `${g_t}T${String(u_h + 1 >= 24 ? u_h - 23 : u_h + 1).padStart(2,'0')}${u_m}00Z`;
          let url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=Randevu+-+${encodeURIComponent(data.isim || "")}&dates=${startStr}/${endStr}`;
          tBtn = `<button onclick="takvimIsaretle(${data.aday_id || data.id}, '${url}')" style="background:#238636; color:white; padding:4px 8px; border:none; border-radius:4px; cursor:pointer; font-size:12px; margin-left:5px;">📅 Takvime Ekle</button>`;
      }
      infoDiv.innerHTML = `📅 <strong>Mevcut Randevu:</strong> ${rTarih} ${rSaat ? "- " + rSaat : ""} ${tBtn} <button onclick="randevuIptalEt(${data.aday_id || data.id})" style="background:#da3633; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:12px; margin-left:5px;">❌ İptal</button>`;
      infoDiv.style.display = "flex";
      infoDiv.style.alignItems = "center";
      infoDiv.style.gap = "5px";
  } else {
      infoDiv.style.display = "none";
  }

  gelismeFormuKapat();
}


function adayKartiKapat() {

  const modal = document.getElementById("aday-modal");

  if (!modal) return;

  modal.classList.add("hidden");

  document.body.style.overflow = "";

  aktifAdayId = null;

  gelismeFormuKapat();
}


function adayGecmisiGoster(gecmis) {

  const kutu = document.getElementById("aday-gecmis");

  if (!kutu) return;

  kutu.innerHTML = "";

  if (!gecmis.length) {

    kutu.innerHTML =
      '<div class="gecmis-bos">Henüz gelişme kaydı bulunmuyor.</div>';

    return;
  }

  for (const olay of gecmis) {

    const item = document.createElement("div");
    item.className = "gecmis-item";

    const tip = olay.olay_tipi || "Not";
    const tarih = olay.tarih || "";

    item.innerHTML = `
      <div class="gecmis-ust">

        <span class="gecmis-tip">
          ${htmlGuvenli(tip)}
        </span>

        <span class="gecmis-tarih">
          ${htmlGuvenli(tarih)}
        </span>

      </div>

      <div class="gecmis-metin">
        ${htmlGuvenli(olay.olay_metni || "Açıklama yok.")}
      </div>

      ${
        olay.durum
          ? `<span class="gecmis-durum">${htmlGuvenli(olay.durum)}</span>`
          : ""
      }
    `;

    kutu.appendChild(item);
  }
}


/* ============================================================
   PROFİL KAYDET
   ============================================================ */

async function adayProfilKaydet() {

  if (!aktifAdayId) return;

  const telefon =
    document.getElementById("kart-telefon").value.trim();

  const email =
    document.getElementById("kart-email").value.trim();

  const adres =
    document.getElementById("kart-adres").value.trim();

  try {

    const r = await fetch(
      `/api/candidates/${aktifAdayId}/profil`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          telefon,
          email,
          adres
        })
      }
    );

    const sonuc = await r.json();

    if (!r.ok || !sonuc.ok) {
      throw new Error(
        sonuc.error || "Bilgiler kaydedilemedi."
      );
    }

    alert("Aday bilgileri kaydedildi.");

  } catch (e) {

    alert("Kayıt hatası: " + e.message);
  }
}


/* ============================================================
   GELİŞME FORMU
   ============================================================ */

function bugununTarihiniAyarla() {

  const input =
    document.getElementById("gelisme-tarih");

  if (!input) return;

  if (input.value) return;

  const d = new Date();

  const yyyy = d.getFullYear();

  const mm = String(
    d.getMonth() + 1
  ).padStart(2, "0");

  const dd = String(
    d.getDate()
  ).padStart(2, "0");

  input.value =
    `${yyyy}-${mm}-${dd}`;
}


function gelismeFormuAc() {

  const form =
    document.getElementById("gelisme-formu");

  if (!form) return;

  form.classList.remove("hidden");

  bugununTarihiniAyarla();

  setTimeout(() => {

    const alan =
      document.getElementById("gelisme-aciklama");

    if (alan) alan.focus();

  }, 50);
}


function gelismeFormuKapat() {

  const form =
    document.getElementById("gelisme-formu");

  if (!form) return;

  form.classList.add("hidden");

  const aciklama =
    document.getElementById("gelisme-aciklama");

  if (aciklama) {
    aciklama.value = "";
  }

  const mesaj =
    document.getElementById("gelisme-mesaj");

  if (mesaj) {
    mesaj.textContent = "";
  }

  const durum =
    document.getElementById("gelisme-durum");

  if (durum) {
    durum.value = "";
  }
}


async function gelismeKaydet() {

  if (!aktifAdayId) {
    alert("Önce bir aday kartı açın.");
    return;
  }

  const tarih =
    document.getElementById("gelisme-tarih").value;

  const olay_tipi =
    document.getElementById("gelisme-tip").value;

  const olay_metni =
    document.getElementById("gelisme-aciklama").value.trim();

  const durum =
    document.getElementById("gelisme-durum").value;

  if (!olay_metni) {

    alert(
      "Lütfen gelişmeyi / görüşme notunu yazın."
    );

    return;
  }

  const mesaj =
    document.getElementById("gelisme-mesaj");

  if (mesaj) {
    mesaj.textContent =
      "⏳ Kaydediliyor...";
  }

  try {

    const r = await fetch(
      `/api/candidates/${aktifAdayId}/gelisme`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tarih,
          olay_tipi,
          olay_metni,
          durum,
          // Checkbox'lar (kart gelisme formundan)
          // v11: Randevu tarihi/saati (frontend input -> POST)
          randevu_tarihi: (() => {
              let t = document.getElementById("gelisme-randevu-tarihi")?.value || "";
              // v18 Esnek Tarih Kalkani: GG/AA/YYYY, GG.AA.YYYY veya YYYY-MM-DD
              t = t.replace(/(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{5,})/, function(match, p1, p2, p3) {
                  return p1 + "/" + p2 + "/" + p3.slice(-4); // Yilin son 4 hanesini al
              });
              return t;
          })(),
          randevu_saati: document.getElementById("gelisme-randevu-saati")?.value || "",
          davet: document.getElementById("gelisme-davet")?.checked ? 1 : 0,
          plan: document.getElementById("gelisme-plan")?.checked ? 1 : 0,
          kayit: document.getElementById("gelisme-kayit")?.checked ? 1 : 0,
          hayir: document.getElementById("gelisme-hayir")?.checked ? 1 : 0
        })
      }
    );

    const sonuc = await r.json();

    if (!r.ok || !sonuc.ok) {
      throw new Error(
        sonuc.error || "Gelişme kaydedilemedi."
      );
    }

    if (mesaj) {
      mesaj.textContent =
        "✅ Gelişme kaydedildi.";
    }

    document.getElementById(
      "gelisme-aciklama"
    ).value = "";

    document.getElementById(
      "gelisme-durum"
    ).value = "";

    await adayKartiAc(aktifAdayId);

    // Listeyi ANINDA yenile (durum degisti)
    if (typeof adaylariYukle === "function") {
      adaylariYukle();
    }

    setTimeout(() => {
      gelismeFormuAc();
    }, 100);

  } catch (e) {

    if (mesaj) {
      mesaj.textContent =
        "❌ " + e.message;
    }
  }
}


/* ============================================================
   ESC ile aday kartını kapat
   ============================================================ */

document.addEventListener(
  "keydown",
  e => {

    if (e.key === "Escape") {

      const modal =
        document.getElementById("aday-modal");

      if (
        modal &&
        !modal.classList.contains("hidden")
      ) {
        adayKartiKapat();
      }
    }
  }
);


/* ============================================================
   EXCEL
   ============================================================ */

async function excelIceAktar() {

  const not =
    document.getElementById("watcher-not");

  if (not) {
    not.textContent = "⏳ okunuyor...";
  }

  try {

    const r = await fetch(
      "/api/excel/import",
      {
        method: "POST"
      }
    );

    const d = await r.json();
    
    // v17 Metrics Timer Stop
    clearInterval(kronoInterval);
    const elKrono = document.getElementById("metrics-krono");
    if (elKrono) elKrono.textContent = `(${((Date.now() - _baslangic) / 1000).toFixed(1)} sn)`;

    if (not) {
      not.textContent =
        d.ok
          ? `✅ ${d.msg}`
          : `❌ ${d.msg}`;
    }

    if (d.ok) {
      adaylariYukle();
    }

  } catch (e) {

    if (not) {
      not.textContent =
        "❌ İçe aktarma hatası: " + e;
    }
  }
}


async function adaySil(id) {

  if (!confirm("Silinsin mi?")) return;

  await fetch(
    `/api/candidates/${id}`,
    {
      method: "DELETE"
    }
  );

  adaylariYukle();
}


/* ============================================================
   CHAT
   ============================================================ */

let streamDevam = false;
let aktifController = null;


function _zamanFormatla(dbZaman) {

  if (!dbZaman) return "";

  const [tarih, saat] =
    dbZaman.split(" ");

  if (!tarih || !saat) {
    return dbZaman;
  }

  const [y, ay, gun] =
    tarih.split("-");

  return `${gun}.${ay} ${saat.slice(0, 5)}`;
}


async function chatYukle() {

  const r =
    await fetch("/api/chat/gecmis");

  const msgs =
    await r.json();

  const kutu =
    document.getElementById("chat-messages");

  if (!kutu) return;

    // Filtre dropdown degerini al
  const filtreEl =
    document.getElementById("kategori-filtre");

  const filtre =
    filtreEl ? filtreEl.value : "hepsi";

  kutu.innerHTML = "";

  for (const m of msgs) {

    // Kategori filtresi
    const mesajKat =
      m.kategori || "sohbet";

    if (
      filtre !== "hepsi" &&
      mesajKat !== filtre
    ) {
      continue;
    }

    mesajGoster(
      m.role,
      m.content,
      {
        zaman: _zamanFormatla(m.zaman),
        model: m.model,
        fallback: m.fallback
      }
    );
  }

  kutu.scrollTop =
    kutu.scrollHeight;
}


function mesajGoster(
  rol,
  icerik,
  opts = {}
) {

  const {
    model = null,
    fallback = false,
    zaman = null,
    liveTimer = false
  } = opts;

  const kutu =
    document.getElementById(
      "chat-messages"
    );

  const wrap =
    document.createElement("div");

  wrap.className =
    `msg-wrap ${rol}`;

  if (
    rol === "assistant" &&
    model
  ) {

    const rozet =
      document.createElement(
        "div"
      );

    rozet.className =
      "model-rozet" +
      (fallback ? " fb" : "");

    rozet.textContent =
      fallback
        ? `🤖 ${model} · FB`
        : `🤖 ${model}`;

    rozet.title =
      fallback
        ? "Bu yanıt fallback modelden geldi"
        : "Yanıtı üreten model";

    wrap.appendChild(rozet);
  }

  const d =
    document.createElement("div");

  d.className =
    `msg ${rol}`;

  d.textContent =
    icerik;

  const meta =
    document.createElement("div");

  meta.className =
    "msg-meta";

  const sol =
    document.createElement("span");

  sol.className =
    "meta-left";

  const zamanEl =
    document.createElement("span");

  zamanEl.className =
    "zaman-damga";

  zamanEl.textContent =
    zaman !== null
      ? zaman
      : (
          liveTimer
            ? new Date().toLocaleTimeString(
                "tr-TR",
                {
                  hour: "2-digit",
                  minute: "2-digit"
                }
              )
            : new Date().toLocaleTimeString(
                "tr-TR"
              )
        );

  sol.appendChild(zamanEl);

  const kronoEl =
    document.createElement("span");

  kronoEl.className =
    "kronometre";

  sol.appendChild(kronoEl);

  meta.appendChild(sol);

  const sag =
    document.createElement("span");

  sag.className =
    "meta-right";

  if (liveTimer) {

    const durBtn =
      document.createElement("button");

    durBtn.textContent =
      "⏹️";

    durBtn.title =
      "Yanıtı durdur";

    durBtn.className =
      "dur-btn";

    durBtn.onclick = () => {

      if (aktifController) {
        aktifController.abort();
      }
    };

    sag.appendChild(durBtn);
  }

  const kopyalaBtn =
    document.createElement("button");

  kopyalaBtn.textContent =
    "📋";

  kopyalaBtn.title =
    "Kopyala";

  kopyalaBtn.onclick = () => {

    navigator.clipboard
      .writeText(d.textContent)
      .then(() => {

        kopyalaBtn.textContent =
          "✅";

        setTimeout(
          () =>
            kopyalaBtn.textContent =
              "📋",
          1200
        );
      });
  };

  const silBtn =
    document.createElement("button");

  silBtn.textContent =
    "🗑️";

  silBtn.title =
    "Bu mesajı sil";

  silBtn.onclick = () =>
    wrap.remove();

  sag.appendChild(kopyalaBtn);
  sag.appendChild(silBtn);

  meta.appendChild(sag);

  wrap.appendChild(d);
  wrap.appendChild(meta);

  kutu.appendChild(wrap);

  kutu.scrollTop =
    kutu.scrollHeight;

  return d;
}


async function chatGonder() {

  if (streamDevam) return;

  const inp =
    document.getElementById(
      "chat-input"
    );

  const metin =
    inp.value.trim();

  if (!metin) return;

  inp.value = "";

  mesajGoster(
    "user",
    metin
  );

  const model =
    document.getElementById(
      "model-select"
    ).value;

  const cevap =
    mesajGoster(
      "assistant",
      "",
      {
        liveTimer: true,
        zaman:
          new Date().toLocaleTimeString(
            "tr-TR"
          ),
        model: model === "otomatik" ? "otomatik (seçiliyor...)" : model
      }
    );

  const wrap =
    cevap.parentElement;

  const kronoEl =
    wrap.querySelector(
      ".kronometre"
    );

  const durBtn =
    wrap.querySelector(
      ".dur-btn"
    );

  const baslangic =
    Date.now();

  const kronometre =
    setInterval(
      () => {

        const sn =
          (
            (Date.now() - baslangic) /
            1000
          ).toFixed(1);

        kronoEl.textContent =
          ` · ⏱️ ${sn} sn`;

      },
      100
    );

  streamDevam = true;

  aktifController =
    new AbortController();

  let durduruldu = false;

  try {

    const r =
      await fetch(
        "/api/chat/stream",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body: JSON.stringify({
            mesaj: metin,
            model
          }),
          signal:
            aktifController.signal
        }
      );

    const reader =
      r.body.getReader();

    const dec =
      new TextDecoder();

    let buf = "";
    let rozetGuncellendi = false;

    while (true) {

      const {
        done,
        value
      } = await reader.read();

      if (done) break;

      buf += dec.decode(
        value,
        {
          stream: true
        }
      );

      const parts =
        buf.split("\n\n");

      buf =
        parts.pop();

      for (const p of parts) {

        if (
          !p.startsWith(
            "data: "
          )
        ) {
          continue;
        }

        try {

          const obj =
            JSON.parse(
              p.slice(6)
            );

          if (obj.model && !rozetGuncellendi) {
            const mevcutRozet = wrap.querySelector(".model-rozet");
            if (mevcutRozet) {
              mevcutRozet.className =
                "model-rozet" +
                (obj.fallback ? " fb" : "");
              mevcutRozet.textContent =
                obj.fallback
                  ? `🤖 ${obj.model} · FB`
                  : `🤖 ${obj.model}`;
              rozetGuncellendi = true;
            }
          }

          if (obj.done) {
            break;
          }

          if (obj.err) {

            cevap.textContent +=
              "\n[HATA] " +
              obj.err;

            continue;
          }

          if (obj.t) {

            cevap.textContent +=
              obj.t;

            const _kutu = document.getElementById("chat-messages");
            if (_kutu) {
              const _enAltMi =
                (_kutu.scrollHeight - _kutu.scrollTop - _kutu.clientHeight) < 80;
              if (_enAltMi) {
                _kutu.scrollTop = _kutu.scrollHeight;
              }
            }
          }

        } catch (e) {
          /* Bozuk paket atlanır */
        }
      }
    }

  } catch (e) {

    if (
      e.name ===
      "AbortError"
    ) {

      durduruldu = true;

      cevap.textContent +=
        "\n⏹️ (durduruldu)";

    } else {

      cevap.textContent +=
        "\n[HATA] " + e;
    }
  } finally {
    // v17 Timer Fix: Hata olsa bile sayaci durdur
    clearInterval(
      kronometre
    );
  }

  const toplamSn =
    (
      (Date.now() - baslangic) /
      1000
    ).toFixed(1);

  kronoEl.textContent =
    durduruldu
      ? ` · ⏹️ ${toplamSn} sn`
      : ` · ${toplamSn} sn`;

  if (durBtn) {
    durBtn.remove();
  }

  streamDevam = false;

  aktifController = null;
}


async function chatTemizle() {

  if (!confirm("Sohbet temizlensin mi?")) {
    return;
  }

  await fetch(
    "/api/chat/temizle",
    {
      method: "POST"
    }
  );

  chatYukle();
}


async function modelleriYukle() {

  const sel =
    document.getElementById(
      "model-select"
    );

  if (!sel) return;

  sel.innerHTML = "";

  const otomatikOpt = document.createElement("option");
  otomatikOpt.value = "otomatik";
  otomatikOpt.textContent = "🤖 Otomatik (Akıllı Seçim)";
  sel.appendChild(otomatikOpt);

  // Model listesi: tek kaynak -> /api/models (config.PRIMARY_MODELS)
  let modeller = [];
  let varsayilan = "";

  try {
    const r = await fetch("/api/models");
    const d = await r.json();
    modeller = d.models || [];
    varsayilan = d.default || "";
  } catch (e) {
    // Endpoint erisilemezse eski liste (guvenli fallback)
    modeller = [
      "qwen2.5:14b",
      "qwen2.5:7b",
      "qwen2.5:3b",
      "llama3.1:latest"
    ];
    varsayilan = "qwen2.5:14b";
  }

  for (const m of modeller) {
    const o = document.createElement("option");
    o.value = m;
    o.textContent = m;
    if (m === varsayilan) o.selected = true;
    sel.appendChild(o);
  }
}


/* ============================================================
   METRİKLER
   ============================================================ */

async function metrikYukle() {

  const kutu =
    document.getElementById(
      "metrik-kutulari"
    );

  if (!kutu) return;

  try {

    const r =
      await fetch(
        "/api/metrics"
      );

    const m =
      await r.json();

    const etiketler = {
      toplam: "Toplam",
      davet: "Davet",
      randevu: "Randevu",
      plan: "Plan",
      kayit: "Kayıt",
      takip: "Takip",
      hayir: "Hayır"
    };

    kutu.innerHTML = "";

    for (
      const [k, lbl]
      of Object.entries(
        etiketler
      )
    ) {

      const deger =
        Number(m[k] || 0);

      const aktifSinif =
        deger > 0
          ? " metric-active"
          : "";

      kutu.innerHTML +=
        `
        <button
          type="button"
          class="metric-card${aktifSinif}"
          onclick="raporMetrikAc('${k}')"
          title="${lbl} adaylarını göster"
        >
          <div class="val">
            ${deger}
          </div>

          <div class="lbl">
            ${lbl}
          </div>

          <div class="metric-hint">
            Görüntüle →
          </div>
        </button>
        `;
    }

    // Blok karti (metrik kartlariyla ayni hizada)
    try {
      const _rb = await fetch("/api/candidates/bloklu");
      if (_rb.ok) {
        const _bl = await _rb.json();
        const _bs = Array.isArray(_bl) ? _bl.length : 0;
        kutu.innerHTML += `
          <button
            type="button"
            class="metric-card blok-metric-card${_bs > 0 ? " metric-active" : ""}"
            onclick="blokModalAc()"
            title="Bloklu adaylar\u0131 g\u00f6ster"
          >
            <div class="val">${_bs}</div>
            <div class="lbl">\u26d4 Blok</div>
            <div class="metric-hint">G\u00f6r\u00fcnt\u00fcle \u2192</div>
          </button>
        `;
      }
    } catch (_e) { /* sessiz */ }

    const oran =
      document.getElementById(
        "oranlar"
      );

    if (oran) {

      oran.textContent =
        `📊 Kaba→Davet: %${m.oran_kabadan_davete ?? 0} · Davet→Randevu: %${m.oran_davetten_randevuya ?? m.davet_randevu_oran ?? 0} · Randevu→Plan: %${m.oran_randevudan_plana ?? 0} · Plan→Kayıt: %${m.oran_plandan_kayda ?? m.plan_kayit_oran ?? 0} · Uçtan uca: %${m.oran_uctan_uca ?? 0}`;
    }

  } catch (e) {

    console.error(
      "Metrik yükleme hatası:",
      e
    );
  }
}


function raporMetrikAc(metrik) {

  if (!metrik) return;

  window.location.href =
    `/?metrik=${encodeURIComponent(metrik)}`;
}

/* ============================================================
   OLLAMA DURUM PİLİ
   ============================================================ */

async function ollamaDurumGuncelle() {

  const pill =
    document.getElementById(
      "ollama-pill"
    );

  const cpuBadge =
    document.getElementById(
      "cpu-badge"
    );

  const gpuBadge =
    document.getElementById(
      "gpu-badge"
    );

  if (!pill) return;

  try {

    const r =
      await fetch(
        "/api/ollama/durum"
      );

    const d =
      await r.json();

    if (cpuBadge) {

      cpuBadge.textContent =
        (
          d.cpu_percent === null ||
          d.cpu_percent === undefined
        )
          ? "CPU --%"
          : `CPU ${Math.round(d.cpu_percent)}%`;
    }

    if (gpuBadge) {

      gpuBadge.textContent =
        d.gpu_aktif
          ? "GPU ✅"
          : "GPU --";
    }

    if (!d.ok) {

      pill.textContent =
        "🔴 Ollama Kapalı";

      pill.className =
        "pill pill-off";

      return;
    }

    if (
      d.models &&
      d.models.length
    ) {

      pill.textContent =
        `✅ Ollama Aktif (${d.models[0].name})`;

      pill.className =
        "pill pill-on";

    } else {

      pill.textContent =
        "🟡 Ollama Boşta";

      pill.className =
        "pill pill-warn";
    }

  } catch (e) {

    pill.textContent =
      "🔴 Ollama Kapalı";

    pill.className =
      "pill pill-off";
  }
}


/* ============================================================
   SİSTEM KAPAT
   ============================================================ */

async function sistemKapat() {

  if (
    !confirm(
      "Sistem ve Ollama kapatılacak. Emin misin?"
    )
  ) {
    return;
  }

  try {

    await fetch(
      "/api/system/kapat",
      {
        method: "POST"
      }
    );

    document.body.innerHTML =
      `
      <div
        style="
          display:flex;
          align-items:center;
          justify-content:center;
          height:100vh;
          font-size:24px;
          color:#c9d1d9;
          background:#0d1117;
          text-align:center;
        "
      >
        ✅ Sistem kapatıldı.<br>
        Bu sekmeyi kapatabilirsiniz.
      </div>
      `;

    setTimeout(
      () => window.close(),
      2000
    );

  } catch (e) {

    alert(
      "Kapatma hatası: " + e
    );
  }
}


/* ============================================================
   BAŞLANGIÇ
   ============================================================ */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    temaUygula();
    gunlukNotYukle();

    adaylariYukle();
    chatYukle();
    modelleriYukle();
    metrikYukle();
    hatirlatmalariYukle();
    sonGelismeleriYukle(); // v17
    blokSayisiGuncelle();
    ollamaDurumGuncelle();
    // v11: Excel bildirimi sadece tarayici acilisinda 1 kez.
    // Sayfa degisince veya yenilendiginde tekrar gosterilmez.
    if (!sessionStorage.getItem("excel_bildirim_gosterildi")) {
      excelBildirimGoster();
      sessionStorage.setItem("excel_bildirim_gosterildi", "1");
    }
    linkedinUrlIzle();

    setInterval(
      ollamaDurumGuncelle,
      5000
    );

    /* v9 Oncelik 2: Excel watcher artik sadece acilista 1 kez calisir.
       Surekli polling CPU/IO mesgul ediyordu ve AI'i yavaslatiyordu.
       Tekrar aktif etmek isterseniz bu blogu acin:
    setInterval(
      excelBildirimGoster,
      5000
    );
    */

    const inp =
      document.getElementById(
        "chat-input"
      );

    if (inp) {

      inp.addEventListener(
        "keydown",
        e => {

          if (
            e.key === "Enter" &&
            !e.shiftKey
          ) {

            e.preventDefault();

            chatGonder();
          }
        }
      );
    }
  }
);

/* ============================================================
   TEMA
   ============================================================ */

function temaUygula() {

  const kayitliTema =
    localStorage.getItem(
      "linkedin_tema"
    ) || "dark";

  document.documentElement.setAttribute(
    "data-theme",
    kayitliTema
  );

  const buton =
    document.getElementById(
      "theme-toggle"
    );

  if (buton) {

    buton.textContent =
      kayitliTema === "dark"
        ? "☀️"
        : "🌙";

    buton.title =
      kayitliTema === "dark"
        ? "Açık temaya geç"
        : "Koyu temaya geç";
  }
}


function temaDegistir() {

  const mevcut =
    document.documentElement.getAttribute(
      "data-theme"
    ) || "dark";

  const yeni =
    mevcut === "dark"
      ? "light"
      : "dark";

  localStorage.setItem(
    "linkedin_tema",
    yeni
  );

  document.documentElement.setAttribute(
    "data-theme",
    yeni
  );

  const buton =
    document.getElementById(
      "theme-toggle"
    );

  if (buton) {

    buton.textContent =
      yeni === "dark"
        ? "☀️"
        : "🌙";

    buton.title =
      yeni === "dark"
        ? "Açık temaya geç"
        : "Koyu temaya geç";
  }
}


/* ============================================================
   GÜNLÜK RAPOR NOTU
   ============================================================ */

function gunlukAnahtar() {

  const d =
    new Date();

  const yyyy =
    d.getFullYear();

  const mm =
    String(
      d.getMonth() + 1
    ).padStart(2, "0");

  const dd =
    String(
      d.getDate()
    ).padStart(2, "0");

  return `linkedin_gunluk_${yyyy}-${mm}-${dd}`;
}


function gunlukNotYukle() {

  const alan =
    document.getElementById(
      "gunluk-not"
    );

  if (!alan) return;

  const kayit =
    localStorage.getItem(
      gunlukAnahtar()
    );

  if (kayit) {

    alan.value =
      kayit;

    const durum =
      document.getElementById(
        "gunluk-not-durum"
      );

    if (durum) {

      durum.textContent =
        "📓 Bugünkü kayıt yüklendi.";
    }
  }
}


function gunlukNotKaydet() {

  const alan =
    document.getElementById(
      "gunluk-not"
    );

  if (!alan) return;

  const metin =
    alan.value.trim();

  const durum =
    document.getElementById(
      "gunluk-not-durum"
    );

  if (!metin) {

    if (durum) {

      durum.textContent =
        "⚠️ Kaydedilecek bir not yok.";
    }

    return;
  }

  localStorage.setItem(
    gunlukAnahtar(),
    metin
  );

  if (durum) {

    durum.textContent =
      "✅ Bugünkü çalışma notu kaydedildi.";
  }
}


function gunlukNotTemizle() {

  const alan =
    document.getElementById(
      "gunluk-not"
    );

  if (alan) {

    alan.value = "";
    alan.focus();
  }

  const durum =
    document.getElementById(
      "gunluk-not-durum"
    );

  if (durum) {

    durum.textContent =
      "";
  }
}


/* ============================================================
   AI ÖNERİ ALANI
   ============================================================ */

async function aiOneriHazirla() {

  const kutu =
    document.getElementById(
      "ai-onerileri"
    );

  if (!kutu) return;

  // v17 Hafiza ve Kalkan v2
  if (sessionStorage.getItem("v17_ai_report_html")) {
    kutu.innerHTML = sessionStorage.getItem("v17_ai_report_html");
    return;
  }

  kutu.innerHTML = `
    <div class="ai-placeholder">
      <div class="ai-icon">⏳</div>
      <div>
        <strong>Analiz ediliyor... <span id="metrics-krono" style="color: #58a6ff; font-size: 18px; font-weight: normal; margin-left: 8px;">(0.0 sn)</span></strong>
        <p>Model huni verisini ve temassızlık sürelerini değerlendiriyor, birkaç saniye sürebilir.</p>
      </div>
    </div>
  `;

  // v17 Metrics Timer Start
  let kronoInterval;
  const _baslangic = Date.now();
  kronoInterval = setInterval(() => {
    const el = document.getElementById("metrics-krono");
    if (el) el.textContent = `(${((Date.now() - _baslangic) / 1000).toFixed(1)} sn)`;
  }, 100);

  try {
    const r = await fetch("/api/metrics/ozet", { method: "POST" });
    const d = await r.json();

    if (!d.ozet) {
      kutu.innerHTML = `
        <div class="ai-placeholder">
          <div class="ai-icon">⚠️</div>
          <div><strong>Öneri alınamadı.</strong></div>
        </div>
      `;
      return;
    }

      if (d.json_veri) {
        const _sonSure = ((Date.now() - _baslangic) / 1000).toFixed(1);
        let html = `<div style="margin-bottom: 12px; font-size: 16px; color: #8b949e; text-align: right; border-bottom: 1px solid #30363d; padding-bottom: 8px;">⏱️ Son Güncelleme: ${_sonSure} sn</div>`;
        html += '<div class="ai-oneri-metin" style="padding: 16px;">';

        // 1. Ozet
        if (d.json_veri.ozet) {
          html += `<div style="margin-bottom: 20px; padding: 12px; background: rgba(56, 139, 253, 0.1); border-left: 4px solid #388bfd; border-radius: 6px;">
            <strong style="color: #58a6ff; font-size: 19px;">📊 Durum Özeti</strong>
            <p style="margin-top: 8px; font-size: 19px; line-height: 1.5; color: #c9d1d9;">${htmlGuvenli(d.json_veri.ozet)}</p>
          </div>`;
        }

        // 2. Oncelikli Adaylar
        if (d.json_veri.oncelikli_adaylar && d.json_veri.oncelikli_adaylar.length > 0) {
          html += `<div style="margin-bottom: 20px;">
            <strong style="color: #f85149; font-size: 19px;">🔥 Öncelikli Adaylar</strong>
            <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">`;
          d.json_veri.oncelikli_adaylar.forEach(a => {
            html += `<div style="padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <strong style="color: #c9d1d9; font-size: 19px;">${htmlGuvenli(a.isim)}</strong>
                <span style="font-size: 16px; padding: 2px 8px; background: #21262d; border-radius: 12px; color: #8b949e;">${htmlGuvenli(a.durum)}</span>
              </div>
              <div style="font-size: 18px; color: #8b949e;">👉 ${htmlGuvenli(a.aksiyon)}</div>
            </div>`;
          });
          html += `</div></div>`;
        }

        // 3. Bugunku Plan
        if (d.json_veri.bugunku_plan && d.json_veri.bugunku_plan.length > 0) {
          html += `<div style="margin-bottom: 20px;">
            <strong style="color: #3fb950; font-size: 19px;">✅ Bugünkü Çalışma Planı</strong>
            <div style="margin-top: 12px; border-left: 2px solid #3fb950; padding-left: 16px; margin-left: 8px;">`;
          d.json_veri.bugunku_plan.forEach(p => {
            html += `<div style="position: relative; margin-bottom: 12px;">
              <div style="position: absolute; left: -23px; top: 2px; width: 12px; height: 12px; background: #3fb950; border-radius: 50%;"></div>
              <strong style="font-size: 18px; color: #c9d1d9;">${htmlGuvenli(p.saat || p.sira + '.')}</strong>
              <div style="font-size: 18px; color: #8b949e; margin-top: 2px;">${htmlGuvenli(p.aksiyon)}</div>
            </div>`;
          });
          html += `</div></div>`;
        }

        // 4. Gozden Kacanlar (Bildirim kutusu)
        if (d.json_veri.gozden_kacanlar && d.json_veri.gozden_kacanlar.length > 0) {
          html += `<div style="margin-top: 20px; padding: 12px; background: rgba(210, 153, 34, 0.1); border: 1px dashed #d29922; border-radius: 6px;">
            <strong style="color: #d29922; font-size: 19px;">⚠️ Gözden Kaçanlar / Riskler</strong>
            <ul style="margin-top: 8px; padding-left: 20px; font-size: 18px; color: #c9d1d9;">`;
          (typeof d.json_veri.gozden_kacanlar === 'string' ? d.json_veri.gozden_kacanlar.split('\n') : (Array.isArray(d.json_veri.gozden_kacanlar) ? d.json_veri.gozden_kacanlar : [d.json_veri.gozden_kacanlar])).forEach(g => {
            html += `<li style="margin-bottom: 6px; line-height: 1.4;">${htmlGuvenli(g)}</li>`;
          });
          html += `</ul></div>`;
        }

        html += '</div>';
        kutu.innerHTML = html;
        sessionStorage.setItem("v17_ai_report_html", html); // v17 Hafiza
      } else {
        // Fallback (Eski format)
      if (d.json_veri) {
        const _sonSure = ((Date.now() - _baslangic) / 1000).toFixed(1);
        let html = `<div style="margin-bottom: 12px; font-size: 16px; color: #8b949e; text-align: right; border-bottom: 1px solid #30363d; padding-bottom: 8px;">⏱️ Son Güncelleme: ${_sonSure} sn</div>`;
        html += '<div class="ai-oneri-metin" style="padding: 16px;">';

        // 1. Ozet
        if (d.json_veri.ozet) {
          html += `<div style="margin-bottom: 20px; padding: 12px; background: rgba(56, 139, 253, 0.1); border-left: 4px solid #388bfd; border-radius: 6px;">
            <strong style="color: #58a6ff; font-size: 19px;">📊 Durum Özeti</strong>
            <p style="margin-top: 8px; font-size: 19px; line-height: 1.5; color: #c9d1d9;">${htmlGuvenli(d.json_veri.ozet)}</p>
          </div>`;
        }

        // 2. Oncelikli Adaylar
        if (d.json_veri.oncelikli_adaylar && d.json_veri.oncelikli_adaylar.length > 0) {
          let a_liste = d.json_veri.oncelikli_adaylar;
          if (!Array.isArray(a_liste)) a_liste = [a_liste];
          
          html += `<div style="margin-bottom: 20px;">
            <strong style="color: #f85149; font-size: 19px;">🔥 Öncelikli Adaylar</strong>
            <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">`;
          a_liste.forEach(a => {
            if (typeof a === 'string') {
                html += `<div style="padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px;"><div style="font-size: 18px; color: #c9d1d9;">${htmlGuvenli(a)}</div></div>`;
            } else {
                html += `<div style="padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="color: #c9d1d9; font-size: 19px;">${htmlGuvenli(a.isim || '')}</strong>
                    <span style="font-size: 16px; padding: 2px 8px; background: #21262d; border-radius: 12px; color: #8b949e;">${htmlGuvenli(a.durum || '')}</span>
                  </div>
                  <div style="font-size: 18px; color: #8b949e;">👉 ${htmlGuvenli(a.aksiyon || '')}</div>
                </div>`;
            }
          });
          html += `</div></div>`;
        }

        // 3. Bugunku Plan
        if (d.json_veri.bugunku_plan && d.json_veri.bugunku_plan.length > 0) {
          let p_liste = d.json_veri.bugunku_plan;
          if (!Array.isArray(p_liste)) p_liste = [p_liste];

          html += `<div style="margin-bottom: 20px;">
            <strong style="color: #3fb950; font-size: 19px;">✅ Bugünkü Çalışma Planı</strong>
            <div style="margin-top: 12px; border-left: 2px solid #3fb950; padding-left: 16px; margin-left: 8px;">`;
          p_liste.forEach(p => {
            if (typeof p === 'string') {
                html += `<div style="position: relative; margin-bottom: 12px;"><div style="position: absolute; left: -23px; top: 2px; width: 12px; height: 12px; background: #3fb950; border-radius: 50%;"></div><div style="font-size: 18px; color: #8b949e;">${htmlGuvenli(p)}</div></div>`;
            } else {
                html += `<div style="position: relative; margin-bottom: 12px;">
                  <div style="position: absolute; left: -23px; top: 2px; width: 12px; height: 12px; background: #3fb950; border-radius: 50%;"></div>
                  <strong style="font-size: 18px; color: #c9d1d9;">${htmlGuvenli(p.saat || p.sira || '')}</strong>
                  <div style="font-size: 18px; color: #8b949e; margin-top: 2px;">${htmlGuvenli(p.aksiyon || p.gorev || '')}</div>
                </div>`;
            }
          });
          html += `</div></div>`;
        }

        // 4. Gozden Kacanlar
        if (d.json_veri.gozden_kacanlar && d.json_veri.gozden_kacanlar.length > 0) {
          let g_liste = d.json_veri.gozden_kacanlar;
          if (typeof g_liste === 'string') {
            g_liste = g_liste.split('\n').map(s => s.replace(/^[-*•]\s*/, '')).filter(s => s.trim());
          } else if (!Array.isArray(g_liste)) {
            g_liste = [String(g_liste)];
          }

          html += `<div style="margin-top: 20px; padding: 12px; background: rgba(210, 153, 34, 0.1); border: 1px dashed #d29922; border-radius: 6px;">
            <strong style="color: #d29922; font-size: 19px;">⚠️ Gözden Kaçanlar / Riskler</strong>
            <ul style="margin-top: 8px; padding-left: 20px; font-size: 18px; color: #c9d1d9;">`;
          g_liste.forEach(g => {
            html += `<li style="margin-bottom: 6px; line-height: 1.4;">${htmlGuvenli(typeof g === 'string' ? g : JSON.stringify(g))}</li>`;
          });
          html += `</ul></div>`;
        }

        html += '</div>';
        kutu.innerHTML = html;
      } else {
        const satirlar = d.ozet.split("\n").filter(s => s.trim() !== "");
        let html = "";
        for (const satir of satirlar) {
          if (satir.startsWith("###") || satir.startsWith("**")) {
            html += `<h4 style="margin-top: 16px; margin-bottom: 8px; color: #c9d1d9;">${satir.replace(/[#*]/g, "").trim()}</h4>`;
          } else {
            html += `<p style="margin: 4px 0; font-size: 19px; line-height: 1.5;">${satir.replace(/^-\s*/, "• ")}</p>`;
          }
        }
        kutu.innerHTML = `<div class="ai-oneri-metin">${html}</div>`;
      }
      }
  } catch (e) {
    kutu.innerHTML = `
      <div class="ai-placeholder">
        <div class="ai-icon">⚠️</div>
        <div><strong>Hata:</strong> ${e}</div>
      </div>
    `;
  } finally {
    // v17 Kalkan v2: Hata olsa bile sayaci durdur
    if (typeof kronoInterval !== 'undefined') {
        clearInterval(kronoInterval);
    }
    const elKrono = document.getElementById("metrics-krono");
    if (elKrono) elKrono.textContent = `(Bitti)`;
  }
}

// ============================================================
// ADAY ARAMA
// ============================================================
function adayAra() {
    const arama = document
        .getElementById("aday-ara")
        .value
        .toLowerCase()
        .trim();

    const satirlar = document.querySelectorAll(
        "#aday-tablo tbody tr"
    );

    let gorunen = 0;

    satirlar.forEach(satir => {
        const metin = satir.textContent.toLowerCase();

        if (arama === "" || metin.includes(arama)) {
            satir.style.display = "";
            gorunen++;
        } else {
            satir.style.display = "none";
        }
    });
}

// ============================================================
// SUTUN SIRALAMA
// ============================================================
let _siralaDurum = { kolon: null, yon: "asc" };

function sirala(kolon) {
  const tbody = document.querySelector("#aday-tablo tbody");
  if (!tbody) return;

  const satirlar = Array.from(tbody.querySelectorAll("tr"));
  if (satirlar.length === 0) return;

  let yon = "asc";
  if (_siralaDurum.kolon === kolon) {
    yon = _siralaDurum.yon === "asc" ? "desc" : "asc";
  }
  _siralaDurum = { kolon, yon };

  const kolonMap = {
    "id": 0, "isim": 1, "tarih": 2, "aciklama": 3,
    "davet": 4, "randevu": 5, "plan": 6, "kayit": 7,
    "takip": 8, "hayir": 9, "is_ariyor": 10
  };

  const idx = kolonMap[kolon];
  if (idx === undefined) return;

  const boolKolonlar = ["davet", "randevu", "plan", "kayit", "takip", "hayir", "is_ariyor"];

  function _tarihParse(s) {
    s = (s || "").trim();
    const m = s.match(/^(\d{1,2})\s+(\d{1,2})\s+(\d{2,4})$/);
    if (!m) return 0;
    let gun = parseInt(m[1]);
    let ay = parseInt(m[2]);
    let yil = parseInt(m[3]);
    if (yil < 100) yil += 2000;
    return new Date(yil, ay - 1, gun).getTime();
  }

  function _norm(s) {
    return (s || "").toString().toLowerCase()
      .replace(/\u0130/g, "i")
      .replace(/\u0131/g, "i")
      .replace(/\u00e7/g, "c")
      .replace(/\u015f/g, "s")
      .replace(/\u011f/g, "g")
      .replace(/\u00fc/g, "u")
      .replace(/\u00f6/g, "o");
  }

  satirlar.sort((a, b) => {
    const aCell = a.children[idx];
    const bCell = b.children[idx];
    if (!aCell || !bCell) return 0;

    const aTxt = aCell.textContent.trim();
    const bTxt = bCell.textContent.trim();

    let aVal, bVal;
    if (kolon === "tarih") {
      aVal = _tarihParse(aTxt);
      bVal = _tarihParse(bTxt);
    } else if (boolKolonlar.includes(kolon)) {
      aVal = aTxt.includes("✓") ? 1 : 0;
      bVal = bTxt.includes("✓") ? 1 : 0;
    } else if (kolon === "id") {
      aVal = parseInt(aTxt) || 0;
      bVal = parseInt(bTxt) || 0;
    } else {
      aVal = _norm(aTxt);
      bVal = _norm(bTxt);
    }

    if (aVal < bVal) return yon === "asc" ? -1 : 1;
    if (aVal > bVal) return yon === "asc" ? 1 : -1;
    return 0;
  });

  satirlar.forEach(tr => tbody.appendChild(tr));

  const ths = document.querySelectorAll("#aday-tablo thead th");
  ths.forEach((th, i) => {
    th.textContent = th.textContent.replace(/\s*[\^v▲▼]\s*$/, "").trim();
    if (i === idx) {
      th.textContent += yon === "asc" ? " ▲" : " ▼";
    }
  });
}


// v11: Sayfa yenilemelerinde tekrar bildirim gostermemek icin localStorage
let _sonExcelZaman = localStorage.getItem("excel_son_zaman") || null;
async function excelBildirimGoster() {

  try {
    const r = await fetch("/api/excel/durum");
    if (!r.ok) return;
    const d = await r.json();

    if (!d.zaman) return;

    // Aynı zaman damgası → atla (bildirim tekrar etmesin)
    if (d.zaman === _sonExcelZaman) return;
    _sonExcelZaman = d.zaman;
    localStorage.setItem("excel_son_zaman", d.zaman);

    // v9: Yeni aday yoksa bildirim gösterme (sadece yeni adayda uyarı)
    if (!d.eklenen || d.eklenen === 0) return;

    // Yeni tarama sonucu → listeyi yenile
    if (typeof adaylariYukle === "function") {
      adaylariYukle();
    }
    const main = document.querySelector("main");
    if (!main) return;

    const eski = document.querySelector(".excel-bildirim");
    if (eski) eski.remove();

    const b = document.createElement("div");
    b.className = "excel-bildirim " + (d.eklenen > 0 ? "yeni" : "bilgi");

    let metin;
    if (d.eklenen > 0) {
      metin = `📥 <strong>${d.eklenen} yeni aday eklendi</strong>`;
      if (d.atlanan > 0) {
        metin += `, ${d.atlanan} zaten mevcuttu`;
      }
    } else {
      metin = `✅ Excel tarandı, yeni aday yok (${d.atlanan} mevcut)`;
    }

    b.innerHTML = `
      <span>${metin} <span class="zaman">(${d.zaman})</span></span>
      <button onclick="this.parentElement.remove()" title="Kapat">✕</button>
    `;

    main.insertBefore(b, main.firstChild);

    setTimeout(() => {
      if (b.parentElement) {
        b.style.opacity = "0";
        setTimeout(() => b.remove(), 300);
      }
    }, 10000);

  } catch (e) {
    console.error("Bildirim hatası:", e);
  }
}

function _siraNumaralariniYenile() {
  const satirlar = document.querySelectorAll("#aday-tablo tbody tr");
  let no = 0;
  for (const tr of satirlar) {
    no++;
    const ilkHucre = tr.querySelector("td");
    if (ilkHucre) {
      ilkHucre.textContent = String(no);
    }
  }
}

async function adaySilOnay(id, isim) {
  const emin = confirm(
    `"${isim}" adlı adayı silmek istediğinizden emin misiniz?\n\n` +
    `Bu işlem GERİ ALINAMAZ!`
  );

  if (!emin) return;

  try {
    const r = await fetch(`/api/candidates/${id}`, {
      method: "DELETE"
    });

    const d = await r.json();

    if (d.ok) {
      const satirlar = document.querySelectorAll("#aday-tablo tbody tr");
      for (const tr of satirlar) {
        if (tr.dataset.adayId === String(id)) {
          tr.style.transition = "opacity 0.3s, transform 0.3s";
          tr.style.opacity = "0";
          tr.style.transform = "translateX(-20px)";
          setTimeout(() => {
            adaylariYukle();
          }, 300);;
          break;
        }
      }
    } else {
      alert("❌ Silme başarısız!");
    }
  } catch (e) {
    console.error("Silme hatası:", e);
  }
}


function yazdirmaModu() {
  const tarihEl = document.getElementById("print-tarih");
  if (tarihEl) {
    const simdi = new Date();
    const formatli = simdi.toLocaleString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
    tarihEl.textContent = "Yazdırma tarihi: " + formatli;
  }

  const eskiBaslik = document.title;
  const simdi = new Date();
  const tarihKisa = simdi.toLocaleDateString("tr-TR").replace(/\./g, "-");
  document.title = `LinkedIn_Aday_Listesi_${tarihKisa}`;

  window.print();

  setTimeout(() => {
    document.title = eskiBaslik;
  }, 1500);
}


document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "p") {
    e.preventDefault();
    yazdirmaModu();
  }
});


function keepModalAc() {
  const modal = document.getElementById("keep-modal");
  if (modal) {
    modal.classList.remove("hidden");
    const ta = document.getElementById("keep-metin");
    if (ta) {
      ta.value = "";
      ta.focus();
    }
    const onizleme = document.getElementById("keep-onizleme");
    if (onizleme) onizleme.classList.add("hidden");
  }
}

function keepModalKapat() {
  const modal = document.getElementById("keep-modal");
  if (modal) modal.classList.add("hidden");
}

async function keepOnizle() {
  const metin = document.getElementById("keep-metin").value.trim();
  if (!metin) {
    alert("Lütfen Keep notunu yapıştırın.");
    return;
  }

  try {
    const r = await fetch("/api/keep/parse", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({metin})
    });
    const d = await r.json();

    if (!d.ok) {
      alert("❌ " + (d.error || "Parse hatası"));
      return;
    }

    const kutu = document.getElementById("keep-onizleme-icerik");
    kutu.innerHTML = `
      <div style="margin-bottom:8px;">
        <strong>Toplam:</strong> ${d.toplam} aday
        &nbsp;|&nbsp;
        <span style="color:#3fb950;">🟢 ${d.yesil} yeşil</span>
        &nbsp;|&nbsp;
        <span style="color:#d29922;">🟡 ${d.sari} sarı</span>
      </div>
      <div style="max-height:200px;overflow-y:auto;font-size:13px;line-height:1.6;">
        ${d.adaylar.map(a => `
          <div style="padding:4px 0;border-bottom:1px solid #21262d;">
            <strong>${a.isim}</strong>${a.durum === 'yeşil' ? '🟢' : a.durum === 'sarı' ? '🟡' : ''}
            <span style="color:#8b949e;"> — ${a.aciklama}</span>
          </div>
        `).join("")}
      </div>
    `;
    document.getElementById("keep-onizleme").classList.remove("hidden");

  } catch (e) {
    alert("❌ Hata: " + e);
  }
}

async function keepAktar() {
  const metin = document.getElementById("keep-metin").value.trim();
  if (!metin) {
    alert("Lütfen Keep notunu yapıştırın.");
    return;
  }

  const btn = event.target;
  btn.disabled = true;
  btn.textContent = "⏳ Aktarılıyor...";

  try {
    const r = await fetch("/api/keep/import", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({metin})
    });
    const d = await r.json();

    if (!d.ok) {
      alert("❌ " + (d.error || "Aktarma hatası"));
      return;
    }

    alert("✅ " + d.mesaj);
    keepModalKapat();

    if (typeof adaylariYukle === "function") adaylariYukle();

  } catch (e) {
    alert("❌ Hata: " + e);
  } finally {
    btn.disabled = false;
    btn.textContent = "✅ Aktar";
  }
}

async function linkedinUrlKaydet() {
  if (!aktifAdayId) {
    alert("Önce bir aday kartı açın.");
    return;
  }

  const input = document.getElementById("kart-linkedin-input");
  if (!input) return;

  const url = input.value.trim();

  if (!url) {
    alert("LinkedIn URL boş olamaz.");
    return;
  }

  try {
    const r = await fetch(`/api/candidates/${aktifAdayId}/linkedin`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ linkedin_url: url })
    });

    const d = await r.json();

    if (!r.ok || !d.ok) {
      alert("❌ " + (d.error || "Kaydedilemedi."));
      return;
    }

    linkedinLinkGuncelle(url);

    if (typeof adaylariYukle === "function") {
      adaylariYukle();
    }

    alert("✅ LinkedIn URL kaydedildi.");

  } catch (e) {
    alert("❌ Hata: " + e);
  }
}

function linkedinLinkGuncelle(url) {
  const input = document.getElementById("kart-linkedin-input");
  const link = document.getElementById("kart-linkedin-link");
  const yok = document.getElementById("kart-linkedin-yok");

  if (!link || !yok) return;

  if (input) {
    input.value = url || "";
  }

  if (url && url.trim()) {
    link.href = url;
    link.style.display = "inline-block";
    yok.style.display = "none";
  } else {
    link.style.display = "none";
    yok.style.display = "block";
  }
}


function isimUrlCikar(url) {
  if (!url) return "";

  const match = url.match(/linkedin\.com\/in\/([^\/\?#]+)/i);
  if (!match) return "";

  let isim = match[1].replace(/-/g, " ");

  try { isim = decodeURIComponent(isim); } catch (e) {}

  isim = isim
    .split(" ")
    .filter(w => w.length > 0)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");

  return isim;
}


function linkedinUrlIzle() {
  const urlInput = document.getElementById("linkedin-url");
  const isimInput = document.getElementById("isim");

  if (!urlInput || !isimInput) return;

  urlInput.addEventListener("change", () => {
    const url = urlInput.value.trim();
    if (!url) return;

    const yeniIsim = isimUrlCikar(url);
    if (yeniIsim) {
      isimInput.value = yeniIsim;
    }
  });

  urlInput.addEventListener("blur", () => {
    const url = urlInput.value.trim();
    if (!url) return;

    const yeniIsim = isimUrlCikar(url);
    if (yeniIsim && !isimInput.value.trim()) {
      isimInput.value = yeniIsim;
    }
  });
}


function durumTopp(durum) {
    return formatStatu(durum).ikon;
}

function durumEtiketi(durum) {
  if (!durum) return "⚪ Değerlendirilecek";
  return String(durum).trim();
}


function aciklamaTemizle(metin) {
  if (!metin) return "";
  let s = String(metin).trim();

  const emojiler = /^(⚪|⚪|🟢|🟡|🔴|🔥|❄️|❄|⚫|🟠|🟨|🟩|🟥|🟧)\s*/u;

  let onceki = "";
  let sayac = 0;
  while (s !== onceki && sayac < 5) {
    onceki = s;
    s = s.replace(emojiler, "").trim();
    sayac++;
  }

  return s;
}

function otomatikStatuBelirle() {
  const olayTipi = document.getElementById("gelisme-tip").value;
  const durumSecici = document.getElementById("gelisme-durum");

  if (!durumSecici) return;

  if (olayTipi === "Plan") {
    durumSecici.value = "🔔 Takip";
  } 
  else if (olayTipi === "Kayıt") {
    durumSecici.value = "🎓 SG";
  } 
  // Hayır: otomatik atama YOK.
  // Kullanici manuel olarak ❄️ DeepFreeze veya ⛔ Blok secer.
}



/* ============================================================
   SÜTUN GENİŞLİĞİ AYARLAMA v2 (aday-tablo)
   - Event delegation: tek document listener
   - MutationObserver: thead yeniden render edilirse tutamaçları yeniler
   - Ayarlar localStorage'da saklanır
   ============================================================ */
(function () {
  const KEY = "aday_tablo_kolon_genislik_v1";
  const TABLO = "#aday-tablo";
  const GRIP_CLASS = "col-resizer";

  let aktifTh = null;
  let baslangicX = 0;
  let baslangicW = 0;

  function thlariAl() {
    return document.querySelectorAll(TABLO + " thead th");
  }

  function yukle() {
    let kayit = {};
    try { kayit = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
    thlariAl().forEach((th, i) => {
      if (kayit[i]) th.style.width = kayit[i];
    });
  }

  function kaydet() {
    const kayit = {};
    thlariAl().forEach((th, i) => {
      kayit[i] = th.style.width || (th.offsetWidth + "px");
    });
    try { localStorage.setItem(KEY, JSON.stringify(kayit)); } catch (e) {}
  }

  function tutamacEkle() {
    thlariAl().forEach((th) => {
      if (th.querySelector("." + GRIP_CLASS)) return;
      const grip = document.createElement("span");
      grip.className = GRIP_CLASS;
      grip.title = "Sürükle: genişliği ayarla · Çift tıkla: sıfırla";
      th.appendChild(grip);
    });
  }

  /* --- TEK global mousemove --- */
  document.addEventListener("mousemove", (e) => {
    if (!aktifTh) return;
    const yeni = Math.max(40, baslangicW + (e.pageX - baslangicX));
    aktifTh.style.width = yeni + "px";
  });

  /* --- TEK global mouseup --- */
  document.addEventListener("mouseup", () => {
    if (!aktifTh) return;
    const eskiTh = aktifTh;
    aktifTh = null;
    document.body.classList.remove("col-resizing");
    const grip = eskiTh.querySelector("." + GRIP_CLASS);
    if (grip) grip.classList.remove("dragging");
    kaydet();
  });

  /* --- Event delegation: mousedown --- */
  document.addEventListener("mousedown", (e) => {
    const grip = e.target.closest && e.target.closest("." + GRIP_CLASS);
    if (!grip) return;
    e.preventDefault();
    e.stopPropagation();

    aktifTh = grip.parentElement;
    baslangicX = e.pageX;
    baslangicW = aktifTh.offsetWidth;

    grip.classList.add("dragging");
    document.body.classList.add("col-resizing");
  });

  /* --- Çift tıklama: sıfırla --- */
  document.addEventListener("dblclick", (e) => {
    const grip = e.target.closest && e.target.closest("." + GRIP_CLASS);
    if (!grip) return;
    e.preventDefault();
    e.stopPropagation();
    const th = grip.parentElement;
    th.style.width = "";
    kaydet();
  });

  /* --- MutationObserver: thead değişirse tutamaçları yenile --- */
  function observerBaslat() {
    const thead = document.querySelector(TABLO + " thead");
    if (!thead) return;
    const obs = new MutationObserver(() => {
      tutamacEkle();
    });
    obs.observe(thead, { childList: true, subtree: true });
  }

  function baslat() {
    yukle();
    tutamacEkle();
    observerBaslat();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", baslat);
  } else {
    baslat();
  }
})();


/* ============================================================
   BLOK LISTESI (Raporlama sayfasi)
   ============================================================ */

async function blokSayisiGuncelle() {
  try {
    const r = await fetch("/api/candidates/bloklu");
    if (!r.ok) return;
    const liste = await r.json();
    const sayi = Array.isArray(liste) ? liste.length : 0;
    const el = document.getElementById("blok-sayisi");
    if (el) el.textContent = String(sayi);
  } catch (e) { /* sessiz */ }
}


async function blokModalAc() {
  const modal = document.getElementById("blok-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  const kutu = document.getElementById("blok-liste");
  if (kutu) kutu.innerHTML = '<div class="blok-bos">Yukleniyor...</div>';

  try {
    const r = await fetch("/api/candidates/bloklu");
    const liste = await r.json();

    if (!Array.isArray(liste) || liste.length === 0) {
      if (kutu) kutu.innerHTML = '<div class="blok-bos">Bloklu aday yok.</div>';
      return;
    }
    blokListeGoster(liste);
  } catch (e) {
    if (kutu) kutu.innerHTML = '<div class="blok-bos">Hata: ' + htmlGuvenli(e.message) + '</div>';
  }
}


function blokListeGoster(liste) {
  const kutu = document.getElementById("blok-liste");
  if (!kutu) return;

  let html = '<table class="blok-tablo"><thead><tr>'
    + '<th>#</th><th>Isim</th><th>Blok Tarihi</th><th>Not</th>'
    + '<th style="text-align:right;">Islem</th>'
    + '</tr></thead><tbody>';

  liste.forEach((a, i) => {
    const isim = htmlGuvenli(a.isim || "?");
    const tarih = htmlGuvenli(a.blok_tarihi || "—");
    const not = htmlGuvenli(a.blok_notu || "—");
    const id = Number(a.id);
    const isimJs = isim.replace(/'/g, "\\'");

    html += '<tr>'
      + '<td>' + (i + 1) + '</td>'
      + '<td><strong>' + isim + '</strong></td>'
      + '<td>' + tarih + '</td>'
      + '<td class="blok-not" title="' + not + '">' + not + '</td>'
      + '<td style="text-align:right; white-space:nowrap;">'
      + '<button class="btn-blok-geri" onclick="blokGeriAl(' + id + ', \'' + isimJs + '\')" title="Bloku kaldir">↺ Geri Al</button>'
      + '<button class="btn-blok-sil" onclick="blokSilOnay(' + id + ', \'' + isimJs + '\')" title="Kalici sil">🗑 Sil</button>'
      + '</td></tr>';
  });

  html += '</tbody></table>';
  kutu.innerHTML = html;
}


function blokModalKapat() {
  const modal = document.getElementById("blok-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  document.body.style.overflow = "";
}


async function blokGeriAl(id, isim) {
  if (!confirm('"' + isim + '" adli adayin bloku kaldirilsin mi?\n\nAday ana listeye geri doner.')) return;

  try {
    const r = await fetch('/api/candidates/' + id + '/blok-kaldir', { method: 'PUT' });
    const d = await r.json();

    if (!r.ok || !d.ok) {
      alert('Hata: ' + (d.error || 'Islem basarisiz.'));
      return;
    }

    await blokModalAc();
    blokSayisiGuncelle();

    if (typeof adaylariYukle === "function") adaylariYukle();
  } catch (e) {
    alert('Hata: ' + e.message);
  }
}


async function blokSilOnay(id, isim) {
  if (!confirm('"' + isim + '" adli aday KALICI olarak silinsin mi?\n\nBu islem geri alinamaz!')) return;

  try {
    const r = await fetch('/api/candidates/' + id, { method: 'DELETE' });
    const d = await r.json();

    if (!d.ok) {
      alert('Silme basarisiz.');
      return;
    }

    await blokModalAc();
    blokSayisiGuncelle();
  } catch (e) {
    alert('Hata: ' + e.message);
  }
}


document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    const modal = document.getElementById("blok-modal");
    if (modal && !modal.classList.contains("hidden")) {
      blokModalKapat();
    }
  }
});


async function hatirlatmalariYukle() {
  const kutu = document.getElementById("hatirlatmalar-listesi");
  if (!kutu) return;

  try {
    const r = await fetch('/api/metrics/hatirlatmalar?t=' + Date.now());
    if (!r.ok) return;
    const liste = await r.json();

    if (!Array.isArray(liste) || liste.length === 0) {
      kutu.innerHTML = `
        <div class="report-empty">
          <div class="report-empty-icon">������</div>
          <strong>Şimdilik kayıtlı hatırlatma yok.</strong>
          <span>Yaklaşan randevular burada görünecek.</span>
        </div>`;
      return;
    }

    kutu.innerHTML = liste.map(h => {
      const guvenli = String(h.metin || "").replace(/</g, "&lt;");
      const ikon = h.ikon || "������";
      const isim = h.isim ? `<strong style="color:#58a6ff;">${h.isim}</strong> - ` : "";
      
      // v18 Takvim Butonu ve Durum Rozeti
      let takvimBtn = "";
      // v18 Filtre: Sadece randevusu olanlarda (saati olanlarda) buton cikar
      if (h.tarih && h.isim && h.saat) {
          const i_str = encodeURIComponent(h.isim);
          let raw_tarih = h.tarih;
          let raw_saat = h.saat || "09:00";
          if (raw_tarih.includes(' ')) {
              let parts = raw_tarih.split(' ');
              raw_tarih = parts[0];
              raw_saat = parts[1] || raw_saat;
          }
          let g_tarih = raw_tarih;
          if (raw_tarih.includes('.')) {
              g_tarih = raw_tarih.split('.').reverse().join('');
          } else if (raw_tarih.includes('-')) {
              g_tarih = raw_tarih.replace(/-/g, '');
          }
          raw_saat = raw_saat.replace('.', ':');
          let g_hh = raw_saat.split(':')[0] || "09";
          let g_mm = raw_saat.split(':')[1] || "00";
          let utc_hh_int = parseInt(g_hh) - 3;
          if (utc_hh_int < 0) utc_hh_int += 24;
          let utc_hh = String(utc_hh_int).padStart(2, '0');
          let end_hh_int = utc_hh_int + 1;
          if (end_hh_int >= 24) end_hh_int -= 24;
          let end_hh = String(end_hh_int).padStart(2, '0');
          
          let startStr = `${g_tarih}T${utc_hh}${g_mm}00Z`;
          let endStr = `${g_tarih}T${end_hh}${g_mm}00Z`;

          const googleUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=Randevu+-+${i_str}&dates=${startStr}/${endStr}`;

          // Backend'den gelen veriye gore kontrol et
          const isAdded = (h.takvime_eklendi == 1);

          if (isAdded) {
              // Takvime eklendiyse YESIL TIK goster
              takvimBtn = `<div style="margin-left: 10px; display: flex; align-items: center; gap: 8px;"><span style="font-size: 13px; color: #3fb950; font-weight: bold; background: rgba(63, 185, 80, 0.1); padding: 4px 8px; border-radius: 4px; border: 1px solid #238636;">✅ Takvimde</span><a href="/api/metrics/takvim?isim=${i_str}&tarih=${encodeURIComponent(raw_tarih)}&saat=${encodeURIComponent(raw_saat)}" style="font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d; color: #c9d1d9; background: #21262d; text-decoration: none;">⬇️ .ics</a></div>`;
          } else {
              // Eklenmediyse TURUNCU ve NABIZ ATAN buton goster
              takvimBtn = `
                <div class="takvim-bekliyor blink" style="display: flex; gap: 5px; margin-left: 10px;">
                  <button onclick="takvimIsaretle(${h.aday_id}, '${googleUrl}')" style="font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #d29922; color: #d29922; background: rgba(210, 153, 34, 0.1); cursor:pointer;">📅 Takvime Ekle</button>
                  <a href="/api/metrics/takvim?isim=${i_str}&tarih=${encodeURIComponent(raw_tarih)}&saat=${encodeURIComponent(raw_saat)}" style="font-size: 12px; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d; color: #c9d1d9; background: #21262d; text-decoration: none; margin-left: 4px;">⬇️ .ics</a>

                </div>`;
          }
      }

      return `
        <div class="hatirlatma-satir hatirlatma-asama-${h.asama}" style="display: flex; align-items: center; justify-content: space-between;">
          <div style="flex: 1;">
            <span class="hatirlatma-ikon">${ikon}</span>
            <span class="hatirlatma-metin">${isim}${guvenli}</span>
          </div>
          <div>${takvimBtn}</div>
        </div>`;
    }).join("");
  } catch (e) {
    console.error("Hatirlatma yukleme hatasi:", e);
  }
}


// v17 JS Font Patch

async function sonGelismeleriYukle() {
  const kutu = document.getElementById("son-gelismeler-listesi");
  if (!kutu) return;
  try {
    const r = await fetch("/api/metrics/son-gelismeler");
    if (!r.ok) return;
    const liste = await r.json();
    if (!Array.isArray(liste) || liste.length === 0) {
      kutu.innerHTML = `<div class="report-empty"><div class="report-empty-icon">⏳</div><strong>Henüz gelişme yok.</strong></div>`;
      return;
    }
    let html = '<div style="display:flex; flex-direction:column; gap:8px;">';
    liste.forEach(g => {
      html += `<div style="font-size:14px; padding:8px; border-bottom:1px solid #30363d;">
        <strong style="color:#58a6ff;">${g.isim}</strong> - <span style="color:#8b949e;">${g.tarih}</span><br>
        <span style="color:#c9d1d9;">${g.olay_tipi}: ${g.olay_metni}</span>
      </div>`;
    });
    html += '</div>';
    kutu.innerHTML = html;
  } catch(e) {
    console.error("Son gelismeler yuklenemedi:", e);
  }
}

// v17 Hatirlatma Isim Fix


// --- v18 Takvim Isaretle ve Iptal Fonksiyonlari ---
async function takvimIsaretle(adayId, url) {
    if (!adayId) return;
    try {
        const res = await fetch('/api/candidates/takvim-isaretle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({aday_id: adayId})
        });
        if (res.ok) {
            // Hatirlatmalar listesini guncelle
            if (typeof hatirlatmalariYukle === 'function') {
                hatirlatmalariYukle(); 
            }
            // Eger aday karti aciksa onu da guncelle (sayfa yenilemesi yerine)
            if (typeof adayKartiKapat === 'function' && document.getElementById('aday-karti')?.style.display !== 'none') {
                // Kart guncelleme fonksiyonu varsa cagirilabilir, yoksa location.reload()
                setTimeout(() => location.reload(), 500);
            }
            // Takvimi yeni sekmede ac
            if (url) window.open(url, '_blank');
        }
    } catch(e) { console.error("Takvim isaretleme hatasi:", e); }
}

async function randevuIptalEt(adayId) {
    if (!adayId) return;
    if (!confirm("Randevuyu iptal etmek istediginize emin misiniz?")) return;
    try {
        const r = await fetch('/api/candidates/randevu-iptal', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({aday_id: adayId})
        });
        if (r.ok) {
            alert("Randevu iptal edildi.");
            location.reload();
        }
    } catch(e) { console.error("Iptal hatasi:", e); }
}

async function aiOneriOnayla(adayId, yeniDurum) {
    if (!confirm(`AI önerisi: "${yeniDurum}" statüsüne geçirilsin mi?`)) return;
    try {
        const r = await fetch(`/api/candidates/${adayId}/otomatik-durum`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({durum: yeniDurum})
        });
        if (r.ok) {
            alert("Statü güncellendi!");
            location.reload();
        } else {
            alert("Hata oluştu.");
        }
    } catch(e) { console.error(e); }
}

// v19 AI Panel

// v19 ics her durumda
