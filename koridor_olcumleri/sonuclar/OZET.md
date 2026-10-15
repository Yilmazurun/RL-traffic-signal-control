# Koridor Olcumu - Ozet

Batipark -> Engiz koridoru (~10,3 km, 10 sinyalize kavsak), 100 test araci.
Her mod icin tum tohumlar ve tum test araclari uzerinden ortalama.
Bu dosya `koridor_seyahat_suresi_olcumu.py --summarize-only` ile yeniden uretilir.

## 1. Bir arac koridoru ortalama ne kadar surede geciyor?

| Mod | Koridorda gecen sure | Ort. hiz | Varsayilana gore | Giris kuyrugunda bekleme | Toplam (bekleme dahil) | Varsayilana gore |
|---|---|---|---|---|---|---|
| Varsayilan (sabit sureli) | **1254 s (20.9 dk)** | 29.6 km/sa | +0.0% | 2199 s (36.6 dk) | 3453 s (57.5 dk) | +0.0% |
| Yesil dalga (rapordaki) | **1240 s (20.7 dk)** | 30.0 km/sa | -1.1% | 2201 s (36.7 dk) | 3440 s (57.3 dk) | -0.4% |
| DQL (rapordaki) | **1040 s (17.3 dk)** | 35.7 km/sa | -17.1% | 2198 s (36.6 dk) | 3238 s (54.0 dk) | -6.2% |
| Yesil dalga (ofset duzeltilmis) | **1099 s (18.3 dk)** | 33.8 km/sa | -12.3% | 2198 s (36.6 dk) | 3297 s (55.0 dk) | -4.5% |
| DQL + guvenlik katmani | **677 s (11.3 dk)** | 54.8 km/sa | -46.0% | 2198 s (36.6 dk) | 2875 s (47.9 dk) | -16.7% |

- **Koridorda gecen sure**: aracin aga girdigi andan koridor sonuna vardigi ana kadar (rapordaki Tablo 4 olcusu).
- **Giris kuyrugunda bekleme**: planlanan kalkis ile aga gercekten girebildigi an arasi. Talepteki araclar girise tek seritten sokuldugu icin tum modlarda ayni; isik kontrolunden bagimsiz.
- **Toplam**: planlanan kalkistan varisa = bekleme + koridorda gecen sure.

## 2. Dagilim (koridorda gecen sure, tum tohumlar)

| Mod | Varan arac | Ortalama | Medyan | En kisa | En uzun |
|---|---|---|---|---|---|
| Varsayilan (sabit sureli) | 500/500 | 1254 s (20.9 dk) | 1203 s (20.1 dk) | 653 s (10.9 dk) | 3206 s (53.4 dk) |
| Yesil dalga (rapordaki) | 500/500 | 1240 s (20.7 dk) | 1130 s (18.8 dk) | 656 s (10.9 dk) | 3406 s (56.8 dk) |
| DQL (rapordaki) | 500/500 | 1040 s (17.3 dk) | 693 s (11.6 dk) | 443 s (7.4 dk) | 5786 s (96.4 dk) |
| Yesil dalga (ofset duzeltilmis) | 500/500 | 1099 s (18.3 dk) | 1070 s (17.8 dk) | 591 s (9.8 dk) | 1842 s (30.7 dk) |
| DQL + guvenlik katmani | 500/500 | 677 s (11.3 dk) | 671 s (11.2 dk) | 491 s (8.2 dk) | 933 s (15.6 dk) |

## 3. Tohum bazinda ortalama koridor suresi (s)

Tohum, SUMO'daki rastgele arka plan trafigini degistirir; test araclari ayni kalir.

| Mod | Tohum 1 | Tohum 2 | Tohum 3 | Tohum 4 | Tohum 5 | Ortalama | Std. sapma |
|---|---|---|---|---|---|---|---|
| Varsayilan (sabit sureli) | 1166 | 1279 | 1322 | 1366 | 1137 | 1254 | 99 |
| Yesil dalga (rapordaki) | 1236 | 1315 | 1208 | 1359 | 1081 | 1240 | 107 |
| DQL (rapordaki) | 820 | 926 | 1037 | 1507 | 908 | 1040 | 272 |
| Yesil dalga (ofset duzeltilmis) | 1031 | 1106 | 1135 | 1136 | 1087 | 1099 | 43 |
| DQL + guvenlik katmani | 684 | 679 | 656 | 672 | 696 | 677 | 15 |

## 4. Guvenlik (kosu basina ortalama, tum araclar)

| Mod | Isinlanma | Acil durus | Sarisiz yesil->kirmizi gecis | Model kararina mudahale |
|---|---|---|---|---|
| Varsayilan (sabit sureli) | 0 | 0 | 0 | - |
| Yesil dalga (rapordaki) | 0 | 0 | 0 | - |
| DQL (rapordaki) | 187 | 82 | 2686 | - |
| Yesil dalga (ofset duzeltilmis) | 0 | 0 | 0 | - |
| DQL + guvenlik katmani | 0 | 0 | 0 | 885 |

- **Isinlanma**: SUMO'nun cok uzun sure kilitli kalan araci ileri tasimasi (sikisma belirtisi).
- **Acil durus**: aracin kirmiziya donen isikta fiziksel sinirin otesinde fren yapmasi.
- **Sarisiz gecis**: bir baglantinin sari yanmadan yesilden kirmiziya donmesi.

## 5. Rapordaki Tablo 4 ile karsilastirma (koridorda gecen sure)

| Mod | Tablo 4 (17 Mayis, tek tohum) | Bugun (tum tohumlar ort.) | Fark |
|---|---|---|---|
| Varsayilan (sabit sureli) | 1336 s (22.3 dk), 100/100 arac | 1254 s (20.9 dk), 500/500 arac | -6.1% |
| Yesil dalga (rapordaki) | 1322 s (22.0 dk), 100/100 arac | 1240 s (20.7 dk), 500/500 arac | -6.2% |
| DQL (rapordaki) | 1071 s (17.9 dk), 94/100 arac | 1040 s (17.3 dk), 500/500 arac | -2.9% |

Fark nedeni: Tablo 4 17 Mayis dosyalariyla uretildi; sonrasinda ag, talep ve 10 modelin 7'si degisti. Tablo 4 ayrica tek tohumdur.
