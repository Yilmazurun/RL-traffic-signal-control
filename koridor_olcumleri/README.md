# Koridor Seyahat Suresi Olcumu

Bu klasor, `-4841` edge'inden `-4779.656.62.62` edge'ine giden (Batipark -> Engiz,
~10,3 km, 10 sinyalize kavsak) 100 test aracinin seyahat suresini olcmek icindir.
Test araclari, egitimde kullanilan talebin (`arac_talepleri/deneme_1.rou.xml`)
ustune eklenir; 0-12000 s arasina sabit tohumla (42) dagitilmistir.

Bu klasordeki betik yalnizca **degerlendirme** yapar: modelleri, ana agi, talep
dosyasini ve detector tanimlarini degistirmez.

## Dosyalar

- `koridor_seyahat_suresi_olcumu.py`: tum modlari calistiran olcum betigi.
- `test_araclari.rou.xml`: sabit tohumla uretilen 100 test araci.
- `default_koridor.sumocfg`: orijinal ag + mevcut trafik + test araclari.
- `dql_koridor.sumocfg`: `default` ile ayni dosyalar; isiklari DQL ajanlari surer (`dql`, `dql_safe`).
- `green_wave_koridor.net.xml/.sumocfg`, `green_wave_offsetleri.csv`: rapordaki yesil dalga (eski ofset).
- `green_wave_fixed_koridor.net.xml/.sumocfg`, `green_wave_fixed_offsetleri.csv`: isareti duzeltilmis ofsetli yesil dalga.
- `detector_koridor.add.xml`: `Detectors/detector_deneme.add.xml`'in ciktilari bu klasore yonlendirilmis kopyasi.
- `sonuclar/eski_tablo4_17mayis/`: rapordaki Tablo 4'u ureten 17 Mayis CSV'leri (commit `34e25b1`), karsilastirma icin.

## Modlar

| Mod | Aciklama |
|---|---|
| `default` | Agdaki sabit sureli programlar. |
| `green_wave` | Rapordaki yesil dalga: 120 s ortak cevrim, 80 km/h. Ofset `(120 - arrival_mod) % 120`. Rapordaki sonuclarla karsilastirma icin **degistirilmedi**. |
| `dql` | Her kavsakta egitilmis DQL ajani. Faz degisiminde agdaki sari faz 3 s kullanilir. Rapordaki davranis, **degistirilmedi**. |
| `green_wave_fixed` | `green_wave` ile ayni faz sureleri; ofset `arrival_mod % 120`. SUMO'da pozitif ofset programi geciktirir (faz 0, t = offset'te baslar), dolayisiyla dogru isaret budur. |
| `dql_safe` | Ayni egitilmis modeller + guvenlik katmani (yeniden egitim yok), asagiya bakiniz. |
| `max_pressure` | Ogrenmesiz Max-Pressure: her kararda yesil verdigi baglantilarin (giris seridi arac - cikis seridi arac) toplami en buyuk faz. Dogru sari gecis, asgari yesil 20 s, karar araligi 10 s. Basinc seridin tamamindaki arac sayisiyla hesaplanir. |
| `max_pressure_safe` | `max_pressure` + `dql_safe` ile ayni azami kirmizi kalkani. |
| `dql_koridor` | `DQL_koridor/` ile egitilen yeni ajanlar. `--koridor-run <kosu>` ile secilir, sonuclarda `dqlk_<kosu>` adiyla gorunur. `--mode hepsi` icine dahil degildir. |

`--mode all` eskisi gibi yalnizca `default`, `green_wave`, `dql` calistirir.
`--mode hepsi` ogrenmesiz ve eski modellerle calisan tum modlari (yedi mod) calistirir. Birden fazla mod bosluklu verilebilir:
`--mode dql dql_safe`.

### dql_safe guvenlik katmani

1. **Dogru sari gecis.** Agdaki sari fazlar yalnizca dongudeki bir sonraki faza gore
   tasarlanmis. Ajan fazlari serbest sirayla secince (or. 0 -> 4) bazi baglantilar
   sari yanmadan kirmiziya geciyordu. `dql_safe` gecis durumunu kendisi uretir:
   mevcut yesilde `G/g`, hedefte `r` olan her baglanti `y`, digerleri mevcut deger.
   Bu durum `setRedYellowGreenState` ile `--safe-yellow` saniye (varsayilan 5) uygulanir,
   sonra `setProgram("0")`, `setPhase(hedef)`, `setPhaseDuration(9999)` ile hedef yesile gecilir.
2. **Azami kirmizi.** `getControlledLinks` ile her action'in yesil verdigi gelen seritler
   cikarilir. Yesil almayan bir seritte duran arac varsa
   (`lane.getLastStepHaltingNumber > 0`) ve o serit `--max-red` saniyedir (varsayilan 90)
   yesil almadiysa, model karari yerine o seridi hizmet eden action secilir.
   Asgari yesil (20 s) ve karar araligi (10 s) aynen gecerlidir.
3. Model kararinin degistirildigi her durum sayilir (`override_count`).

## Calistirma (PowerShell)

```powershell
# Dosyalari hazirla (test araclari, yesil dalga aglari, sumocfg)
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --prepare-only

# Rapordaki uc mod, tek tohum (eski davranis)
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode all --seed 1

# Tek mod
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql_safe --seed 1 --max-steps 36000

# Bes mod x uc tohum, 4 paralel SUMO sureci
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode hepsi --seeds 1 2 3 --max-steps 36000 --jobs 4

# dql_safe parametreleri
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql_safe --max-red 120 --safe-yellow 4

# Yesil dalga ofsetlerini TraCI ile dogrula (faz 0 offset saniyesinde mi basliyor?)
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --verify-offsets

# Sadece ozet CSV'lerini sonuclar\ozetler\ altindaki kosu ozetlerinden yeniden uret
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --summarize-only

# GUI'de izle (CSV yazilmaz)
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql_safe --show-corridor
```

Bir kosu (tek mod, tek tohum) bu makinede 10-30 dakika surer. Uzun kosular icin
`--jobs` ile paralel calistirin; her surecin konsol ciktisi
`sonuclar\konsol_{mod}_s{tohum}.txt` dosyasina yazilir.

### Bayraklar

| Bayrak | Varsayilan | Aciklama |
|---|---|---|
| `--mode` | `all` | `default`, `green_wave`, `dql`, `green_wave_fixed`, `dql_safe`, `all`, `hepsi`; birden fazla verilebilir |
| `--seed` | 1 | SUMO tohumu (talepteki olasilikli flow'lari etkiler; test araclari sabit) |
| `--seeds` | - | Birden fazla tohum; `--seed` yerine gecer |
| `--max-steps` | 24000 | Olcumun azami suresi (s). Dongu ayrica tum test araclari varinca veya agda arac kalmayinca biter |
| `--jobs` | 1 | Paralel SUMO sureci sayisi |
| `--max-red` | 90 | `dql_safe` azami kirmizi suresi (s) |
| `--safe-yellow` | 5 | `dql_safe` sari suresi (s) |
| `--no-diagnostics` | kapali | tripinfo/statistic/log ciktilarini kapatir (o zaman isinlanma/acil durus sutunlari bos kalir) |
| `--verify-offsets` | - | Yesil dalga ofset dogrulamasi (`sonuclar\ofset_dogrulama.csv`) |
| `--summarize-only` | - | Sadece ozet CSV'leri yeniden uretir |
| `--prepare-only`, `--gui`, `--show-corridor`, `--allow-missing-models` | - | Onceki gibi |

## Cikti dosyalari (`sonuclar/`)

Her mod x tohum kosusu kendi dosyalarina yazar, birbirinin uzerine yazmaz:

| Dosya | Icerik |
|---|---|
| `{mod}_s{tohum}_travel_times.csv` | Varan her test araci icin bir satir |
| `tripinfo_{mod}_s{tohum}.xml` | SUMO tripinfo (`write-unfinished` acik: varamayanlar `arrival="-1"`) |
| `stats_{mod}_s{tohum}.xml` | SUMO istatistikleri (`teleports`, `safety`) |
| `log_{mod}_s{tohum}.txt` | SUMO uyarilari (isinlanma, acil durus) |
| `eksik_araclar_{mod}_s{tohum}.csv` | Varamayan her test araci: `girmedi` / `takildi` / `planlanan_zaman_gelmedi`, serit, kavsak, bekleme |
| `ozetler/ozet_{mod}_s{tohum}.csv` | Kosu ozeti (tek satir) |
| `karsilastirma_ozet.csv` | Tum kosu ozetleri (mod, tohum) |
| `karsilastirma_coklu_tohum.csv` | Her mod icin tohumlar arasi ortalama ve standart sapma |
| `ofset_dogrulama.csv` | `--verify-offsets` sonucu |
| `konsol_{mod}_s{tohum}.txt` | `--jobs` ile calisan sureclerin konsol ciktisi |

Detector ciktilari `detector_ciktilari/{mod}_s{tohum}/` altina gider.
`tripinfo_*`, `stats_*`, `log_*`, `konsol_*` ve `detector_ciktilari/` git'e eklenmez.

## Metrikler

Zamanlar 1 s adimla, adim sonu zamani olarak kaydedilir.

| Sutun | Tanim |
|---|---|
| `planned_depart_time` | `test_araclari.rou.xml` icindeki `depart` |
| `depart_time` | Aracin aga fiilen girdigi an |
| `arrival_time` | Aracin koridor sonuna vardigi an |
| `travel_time` | `arrival - depart` (rapordaki Tablo 4 metrigi; giris kuyrugunda beklemeyi saymaz) |
| `insertion_delay` | `depart - planned_depart` (giris kuyrugunda bekleme) |
| `total_time` | `arrival - planned_depart` = `travel_time + insertion_delay` (**ana metrik**) |
| `completed_vehicle_count` | Olcum bitene kadar varan test araci |
| `never_departed_count` | Hic kalkamayan test araci |
| `departed_not_arrived_count` | Kalkip varamayan test araci |
| `teleport_count` | Tum araclar icin isinlanma (`stats` -> `teleports total`) |
| `emergency_stop_count` | Tum araclar icin acil durus (`stats` -> `safety emergencyStops`) |
| `red_light_emergency_stop_count` | Log'da "because of a red traffic light" acil duruslari |
| `yellowless_red_switch_count` | Koridordaki 10 kavsakta sari yanmadan `G/g -> r` olan baglanti gecisi sayisi |
| `override_count` | `dql_safe`: model karari yerine azami kirmizi kuralinin sectigi action sayisi |
| `top_teleport_flows` | En cok isinlanan 5 flow |

Ortalama seyahat ve toplam sureler yalnizca **varan** araclar uzerinden hesaplanir.
Tamamlanan sayisi farkli olan kosularda ortalamalar dogrudan karsilastirilmamalidir
(varamayanlar genelde en son yola cikan, en uzun sureli araclardir).

## Sonuclar (14 Ekim 2026, SUMO 1.26.0, Windows)

Bugunku dosyalarla, 5 tohum (1-5), her kosuda 100/100 test araci vardi
(hic kalkamayan veya takilan arac yok; tum kosular 24000 s dolmadan, ~16700-19000 s'de bitti).
Kaynak: `sonuclar/karsilastirma_coklu_tohum.csv`, kosu bazinda `sonuclar/karsilastirma_ozet.csv`.

| Mod | Seyahat (s) | Toplam (s) | Giris gecikmesi (s) | Isinlanma | Acil durus | Sarisiz G->r | Mudahale |
|---|---|---|---|---|---|---|---|
| default | 1253.8 +- 99.0 | 3452.7 +- 145.4 | 2198.9 | 0.2 | 0 | 0 | - |
| green_wave | 1239.7 +- 107.2 | 3440.4 +- 165.2 | 2200.7 | 0 | 0 | 0 | - |
| dql | 1039.6 +- 272.2 | 3237.7 +- 265.2 | 2198.0 | 187.2 | 82.4 | 2685.6 | - |
| green_wave_fixed | 1099.0 +- 43.3 | 3297.2 +- 98.1 | 2198.2 | 0 | 0.2 | 0 | - |
| dql_safe | 677.3 +- 14.8 | 2875.0 +- 80.3 | 2197.7 | 0 | 0 | 0 | 885.2 |

(ortalama +- tohumlar arasi standart sapma; isinlanma/acil durus tum araclar icin, kosu basina)

Rapordaki Tablo 4 (17 Mayis, tek tohum, `sonuclar/eski_tablo4_17mayis/`):
varsayilan 1335.95 s (100/100), yesil dalga 1321.57 s (100/100), DQL 1071.06 s (94/100).

Notlar:

- **Fark nedeni.** Tablo 4, 17 Mayis'taki dosyalarla uretildi (commit `34e25b1`). Sonrasinda
  ag dosyasi (or. Pelitkoy sari fazi), talep dosyasi ve 10 modelin 7'si degisti. Ayrica Tablo 4
  tek tohumdur; bugun ayni modda tohumlar arasi fark 100-270 s'dir.
- **Giris gecikmesi tum modlarda ayni (~2200 s).** Talepteki flow'larda `departLane` yok
  (varsayilan: ilk serit, hiz 0). `-4841` girisinden 3000-7000 s arasinda 0.65 arac/s
  sokulmaya calisiliyor; giris kuyrugu isik kontrolunden bagimsiz buyuyor ve test araclari
  da bu kuyrukta bekliyor. Bu nedenle `total_time` modlari `travel_time` kadar ayirir,
  ama gercek yolculuk suresini (~2900-3450 s) gosterir.
- **dql.** Tum araclar varsa da her kosuda ~2700 baglanti sari yanmadan kirmiziya geciyor,
  ~82 "kirmizi isik nedeniyle acil durus" ve ~187 isinlanma (cogu `yesilyurt_e_1`) oluyor.
  Tohumlar arasi sapma da yuksek (+- 272 s).
- **dql_safe.** Ayni modeller; sari gecis duzeltmesi acil duruslari ve sarisiz gecisleri
  sifirliyor, baglanti bazli azami kirmizi kurali isinlanmalari sifirliyor. Model kararlarinin
  kabaca %5'i degistiriliyor (kosu basina ~885 mudahale, 10 kavsak). Ilk surumde kural
  serit bazliydi; `yesilyurt_avm_kavsak` E70_0 seridinin bir baglantisi her fazda yesil
  oldugu icin E34 yonundeki aclik gorulmuyordu (41 isinlanma kaldi). Bu surumun ozetleri
  `sonuclar/dql_safe_serit_bazli_v1/` altinda.
- **green_wave_fixed.** Ofset isaretinin duzeltilmesi seyahat suresini ~140 s (%11) azaltti;
  eski `green_wave` varsayilandan anlamli farkli degil.
