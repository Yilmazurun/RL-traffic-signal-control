# DQL_koridor – Kalkanli, cok metrikli, koridor farkindalikli DQN

Eski DQL'in (`DQL_bekleme_suresi/`) olcumlerde gorulen sorunlarina yonelik yeni yontem.
Eski modeller ve egitim dosyalari degistirilmez; bu klasor bagimsizdir.

## Neden

Koridor olcumleri (`koridor_olcumleri/SONUC_RAPORU.md`) su sorunlari gosterdi:

| Sorun | Bu yontemdeki karsiligi |
|---|---|
| Odul yalnizca yerel bekleme; Turgut Ozal ajani koridoru 52 dk kirmizida tutabiliyor | Birlesik odul: bekleme + basinc (PressLight) + aclik cezasi |
| Egitim 12000 s'de bitiyor, ajanlar talep sonrasi bosalmayi hic gormedi | Bolum 19000 s (veya ag bosalana kadar) |
| Azami kirmizi kurali sonradan eklenmis; ajan bunu ogrenmedi | Kalkan egitim sirasinda da acik (shielded RL) |
| Her ajan, digerleri sabit programdayken tek basina egitildi | 10 ajan ayni simulasyonda birlikte egitilir |
| Epsilon ilk bolumun yarisinda 0.05'e iniyordu | Epsilon bolum basina azalir (1.0 -> 0.05, ~20 bolum) |
| Ajan komsu kavsaklari ve yaklasan araclari gormuyor | Durum: duran/hareketli ayrimi, kirmizi yasi, komsu kuyrugu |

## Yontem

**Durum** (kavsak basina):
- Her detector grubu icin duran ve hareketli arac sayisi (/40) – Advanced-XLight
- Her action icin "kac saniyedir yesil almadi" (/120)
- Mevcut faz (one-hot) ve fazin suresi (/60)
- Koridordaki onceki ve sonraki kavsagin ana yol kuyrugu (/40) – CoLight'in sade hali

**Odul** (`reward = combo`):

```
maliyet = w_wait * bekleme/1000 + w_pressure * |basinc|/100 + w_starve * aclik + 0.5 * faz_degisti
odul    = max(-10, -0.1 * maliyet)
```

- bekleme: detector alanindaki araclarin toplam bekleme suresi (eski odul)
- basinc: tum kontrollu baglantilar icin (giris seridi arac - cikis seridi arac) toplami
- aclik: bekleyen araci olan en uzun kirmizi baglantinin 60 s'yi asan kismi (/30)

**Kalkan**: 90 s'dir kirmizi olan ve onu kullanmak icin bekleyen arac bulunan bir baglanti
varsa, ajanin secimi o baglantiya yesil veren action ile degistirilir. Ogrenmede gercekte
uygulanan action kullanilir. Dogru sari gecis (5 s, yesilden kirmiziya donen her baglanti
sari) her zaman aciktir.

**Ogrenme**: Double DQN, Huber kaybi, Adam (lr 5e-4), gamma 0.95, bellek 50000,
batch 64, hedef ag her 1000 adimda guncellenir. Ag mimarisi eski modelle ayni
(2 x 128), boylece fark yalnizca durum/odul/egitim ortamindan gelir.
Egitim tohumlari 1001, 1002, ...; olcum tohumlari (1-5) ile cakismaz.

## Egitim (parca parca)

Her bolum sonunda tum durum `egitimler/<kosu>/checkpoint.pt` dosyasina yazilir.
Ayni komut tekrar calistirilinca kaldigi yerden devam eder. Bir bolum bu
makinede ~15-25 dakika surer; tam egitim ~30 bolum.

```powershell
# 3 bolum calistir, kapat; sonra ayni komutla devam et
python DQL_koridor\train_koridor.py --run ana --episodes 3
```

Durdurmak icin:
- `Ctrl+C`: yarim bolum kaydedilmez, son tam bolumden devam edilir.
- `egitimler\<kosu>\DUR` adli bos dosya: mevcut bolum bitince durur.

```powershell
New-Item DQL_koridor\egitimler\ana\DUR
```

Ilerleme: `egitimler\<kosu>\egitim_log.csv` (bolum basina varan arac, ortalama seyahat,
isinlanma, acil durus, odul bilesenleri, kalkan mudahalesi, kayip).

## Ablasyon kosulari

Her bilesenin katkisini olcmek icin ayri kosular (ayni bolum sayisiyla):

| Kosu | Komut ek bayraklari | Ne olculur |
|---|---|---|
| `ana` | – | Tam yontem |
| `abl_odul_bekleme` | `--reward wait` | Birlesik odulun katkisi |
| `abl_kalkansiz` | `--no-shield` | Kalkanli egitimin katkisi |
| `abl_komsusuz` | `--no-neighbors` | Komsu bilgisinin katkisi |
| `abl_durum_sade` | `--no-moving --no-red-age` | Zengin durumun katkisi |

```powershell
python DQL_koridor\train_koridor.py --run abl_kalkansiz --no-shield --episodes 3
```

Bir kosunun ayarlari ilk calistirmada `ayarlar.json`'a yazilir ve sonradan degistirilemez.

## Olcum

Egitilen modeller koridor olcum betigiyle, diger modlarla ayni kosullarda olculur:

```powershell
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql_koridor --koridor-run ana --seeds 1 2 3 4 5 --max-steps 36000 --jobs 5
# Birden fazla kosu:
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql_koridor --koridor-run ana abl_kalkansiz --seeds 1 2 3 4 5 --max-steps 36000 --jobs 5
```

Sonuclarda mod adi `dqlk_<kosu>` olur (`sonuclar/OZET.md`, `karsilastirma_coklu_tohum.csv`).

## Dosyalar

| Dosya | Icerik |
|---|---|
| `koridor_ajan.py` | Ajan: durum, odul, kalkan, faz gecisi, ag (egitim ve olcum ortak) |
| `train_koridor.py` | Cok ajanli, devam ettirilebilir egitim |
| `egitimler/<kosu>/ayarlar.json` | Kosunun ayarlari |
| `egitimler/<kosu>/modeller.pt` | Son bolumun agirliklari (olcumde kullanilir) |
| `egitimler/<kosu>/modeller_bolum_XXX.pt` | Her 5 bolumde bir agirlik kopyasi |
| `egitimler/<kosu>/checkpoint.pt` | Devam icin tam durum (buyuk, git'e eklenmez) |
| `egitimler/<kosu>/egitim_log.csv` | Bolum bazinda egitim gostergeleri |
