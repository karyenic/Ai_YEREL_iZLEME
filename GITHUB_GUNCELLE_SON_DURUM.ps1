# ============================================================
# AI_YEREL-LiNKEDiN_TAKiP
# GITHUB_GUNCELLE_SON_DURUM.ps1
#
# Amac:
# 1) Yerel repo durumunu kontrol eder.
# 2) Projenin mevcut stratejik durumunu PROJECT_STATE.md olarak kaydeder.
# 3) Git snapshot olusturur.
# 4) main branch'i origin/main ile gunceller.
# 5) Degisiklikleri commit + push eder.
#
# Kullanim:
# powershell -ExecutionPolicy Bypass -File .\GITHUB_GUNCELLE_SON_DURUM.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$Repo = "C:\AI_YEREL\LiNKEDiN_TAKiP"
$Branch = "main"
$Remote = "origin"

function Write-Step($n, $text) {
    Write-Host ""
    Write-Host "[$n] $text" -ForegroundColor Cyan
}

function Run-Git([string[]]$Args) {
    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Git komutu basarisiz oldu: git $($Args -join ' ')"
    }
}

Write-Host "============================================================"
Write-Host " AI_YEREL-LiNKEDiN_TAKiP - GITHUB SON DURUM GUNCELLEME"
Write-Host "============================================================"

if (-not (Test-Path -LiteralPath $Repo)) {
    throw "Repo bulunamadi: $Repo"
}

Set-Location -LiteralPath $Repo

Write-Step "1/7" "Git repo kontrol ediliyor..."
if (-not (Test-Path -LiteralPath (Join-Path $Repo ".git"))) {
    throw "Bu klasor Git repository degil: $Repo"
}

$remoteUrl = (& git remote get-url $Remote 2>$null)
if ($LASTEXITCODE -ne 0) {
    throw "origin remote bulunamadi."
}

Write-Host "Repo   : $Repo"
Write-Host "Branch : $Branch"
Write-Host "Origin : $remoteUrl"

Write-Step "2/7" "Branch ve uzak repo senkronizasyonu..."
Run-Git @("checkout", $Branch)
Run-Git @("fetch", $Remote)

Write-Step "3/7" "Proje stratejik son durum dosyasi yaziliyor..."

$state = @"
# AI_YEREL-LiNKEDiN_TAKiP - Proje Son Durum

Guncelleme tarihi: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## 1. Ana veri modeli

Adayin temel kimligi ve mevcut durumu ile surec/gecmis birbirinden ayrilacaktir.

### ADAY PROFILI
- id
- isim
- linkedin_url
- telefon
- email
- adres
- kayit_tarihi
- durum

### SUREC / OLAY GECMISI
Adayla ilgili gerceklesen islemler ve notlar olay/gecmis olarak tutulabilir:
- Gorüsme
- Not
- Davet
- Randevu
- Plan
- Takip
- Kayit sonrasi baslatma
- Diger surec olaylari

## 2. Ana aday durumlari

Adayin tek bir guncel ana durumu olacaktir:

- 🔥 Sicak
- 🟢 Aktif
- ⚪ Degerlendirilecek
- ❄️ DeepFreeze
- 🔴 Olumsuz

## 3. Durumlarin yasam dongusu

Yeni aday ilk kez programa girdiginde:

- 🔥 Sicak
- 🟢 Aktif
- ⚪ Degerlendirilecek

secenekleri kullanilabilir.

Asagidaki durumlar ilk kayitta ana durum olarak secilmemelidir:

- ❄️ DeepFreeze
- 🔴 Olumsuz

Bunlar surec icerisinde ortaya cikabilecek sonuc durumlaridir.

DeepFreeze kalici arsiv/silme anlamina gelmez. Gerektiginde aday tekrar:
- 🔥 Sicak
- 🟢 Aktif
- ⚪ Degerlendirilecek

durumlarindan birine alinabilir.

## 4. Eski statulerin yeni anlamlandirilmasi

Asagidaki alanlar adayin ana statuleri olmaktan cikarilmalidir:

- 🆕 Yeni
- 🟡 Bekliyor
- 🔔 Takip
- 🚀 Kayit Sonrasi Baslatma

Bunlar gerekiyorsa olay/gecmis kaydi olarak tutulabilir.

Ayrica eski checkbox mantigi:
- Davet
- Randevu
- Plan
- Kayit
- Takip
- Hayir
- Is Ariyor

tek bir "ana durum" mantigi ile karistirilmamalidir. Gereken bilgiler surec olaylari/gecmisi olarak modellenmelidir.

## 5. Kayit Tarihi kurali

"Kayıt Tarihi" adayın bu programa ilk kez kaydedildigi tarihtir.

Kaynak ne olursa olsun:
- Excel
- Keep
- Manuel giris
- Gelecekte eklenecek baska kaynaklar

aday ilk kez programa girdigi anda program kayit tarihi olusturulur.

Bu tarih:
- tekrar Excel aktariminda degismemeli,
- Keep tekrar aktariminda degismemeli,
- mevcut aday guncellendiginde degismemeli,
- kaynak dosyanin/eski notun tarihi tarafindan ezilmemelidir.

Kaynak veya olay tarihi gerekiyorsa ayri olay/gecmis alaninda tutulmalidir.

## 6. Aday kimligi

LinkedIn URL mevcutsa aday eslestirmede guclu kimlik olarak kullanilmalidir.

Ayni adli kisilerin yanlis birlestirilmesini onlemek icin isim tek basina guvenilir ana kimlik olarak kullanilmamalidir.

## 7. UI hedefi

Aday listesi sadeletilecektir:

ID | Isim | Kayit Tarihi | Aciklama | Durum | Islem

"Sil" butonu, "Islem" basliginin altinda yer almalidir.

## 8. AI stratejisi

AI modelinin karar/strateji uretmesi icin:

1. Aday profili
2. Mevcut ana durum
3. Olay/gecmis kayitlari
4. Son gelismeler
5. Kaynak bilgisi

ayri katmanlar olarak modele sunulmalidir.

Model, eski checkbox/status alanlarini adayın mevcut ana durumu ile karistirmamalidir.

## 9. Bu asamanin amaci

Bu commit kod davranisini degistirmekten once projenin veri ve surec mimarisini net bir referans halinde GitHub'da saklamaktir.

Sonraki kodlama adiminda once:
- database.py
- excel_io.py
- routes/keep.py
- routes/candidates.py
- static/app.js
- templates/index.html

arasindaki veri akisinin tamamlanmasi ve mevcut migration/schema durumunun kontrol edilmesi gerekir.

Kod degisikligi bu haritalama sonrasinda, kucuk ve test edilebilir adimlarla yapilmalidir.
"@

$statePath = Join-Path $Repo "PROJECT_STATE.md"
Set-Content -LiteralPath $statePath -Value $state -Encoding UTF8
Write-Host "Olusturuldu: $statePath"

Write-Step "4/7" "Mevcut degisiklikler listeleniyor..."
git status --short

Write-Step "5/7" "Tum proje snapshot'i hazirlaniyor..."
Run-Git @("add", "-A")

$staged = (& git diff --cached --name-only)
if ([string]::IsNullOrWhiteSpace(($staged -join "`n"))) {
    Write-Host ""
    Write-Host "Commit edilecek yeni degisiklik yok." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Commit edilecek dosyalar:"
    $staged | ForEach-Object { Write-Host "  $_" }

    $commitMessage = "chore: record current project strategy and status model"
    Run-Git @("commit", "-m", $commitMessage)
}

Write-Step "6/7" "main -> origin/main durumu kontrol ediliyor..."
Run-Git @("fetch", $Remote)

$localSha = (& git rev-parse $Branch)
$remoteSha = (& git rev-parse "$Remote/$Branch")

Write-Host "Local : $localSha"
Write-Host "Remote: $remoteSha"

if ($localSha -ne $remoteSha) {
    $behind = [int](& git rev-list --count "$Branch..$Remote/$Branch")
    $ahead  = [int](& git rev-list --count "$Remote/$Branch..$Branch")

    Write-Host "Ahead : $ahead"
    Write-Host "Behind: $behind"

    if ($behind -gt 0 -and $ahead -eq 0) {
        Write-Host "Uzak repo onde. Fast-forward pull yapiliyor..."
        Run-Git @("pull", "--ff-only", $Remote, $Branch)
    }
    elseif ($behind -gt 0 -and $ahead -gt 0) {
        throw "Local ve origin/main birbirinden ayrilmis. Otomatik merge yapilmadi; once durum manuel olarak incelenmeli."
    }
}

Write-Step "7/7" "GitHub'a push ediliyor..."

$localSha = (& git rev-parse $Branch)
$remoteSha = (& git rev-parse "$Remote/$Branch")

if ($localSha -ne $remoteSha) {
    Run-Git @("push", $Remote, $Branch)
} else {
    Write-Host "Push gerekmiyor; local ve origin/main ayni committe."
}

Write-Host ""
Write-Host "============================================================"
Write-Host " SON DURUM"
Write-Host "============================================================"
git status --short
Write-Host ""
Write-Host "HEAD:"
git log -1 --oneline
Write-Host ""
Write-Host "GitHub guncellemesi tamamlandi."
Write-Host "PROJECT_STATE.md GitHub'da proje stratejik referansi olarak tutuluyor."
Write-Host ""
