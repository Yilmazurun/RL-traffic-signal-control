# Koridor Ölçümü – Sonuç Raporu

Batıpark → Engiz koridoru (~10,3 km, 10 sinyalize kavşak). Ölçümler 14–15 Ekim 2026'da,
Windows 10 + SUMO 1.26.0 ile, eğitilmiş modeller değiştirilmeden yapıldı.

## 1. Kısa sonuç

**Raporda kullanılacak ana tablo** (5 tohum × 100 test aracı = mod başına 500 araç, hepsi vardı):

| Mod | Koridorda geçen süre (ort.) | Varsayılana göre | Tohumlar arası sapma | En yavaş araç |
|---|---|---|---|---|
| Varsayılan (sabit süreli) | **1254 s (20,9 dk)** | – | ± 99 s | 53,4 dk |
| Yeşil dalga (rapordaki, ofset hatalı) | **1240 s (20,7 dk)** | −1,1 % | ± 107 s | 56,8 dk |
| Yeşil dalga (ofset düzeltilmiş) | **1099 s (18,3 dk)** | −12,3 % | ± 43 s | 30,7 dk |
| DQL (rapordaki) | **1040 s (17,3 dk)** | −17,1 % | ± 272 s | 96,4 dk |
| DQL + güvenlik katmanı (`dql_safe`) | **677 s (11,3 dk)** | −46,0 % | ± 15 s | 15,6 dk |

"Koridorda geçen süre", aracın ağa girdiği andan koridor sonuna vardığı ana kadardır
(rapordaki Tablo 4 ile aynı ölçü).

Önemli iki not:

1. **DQL'in ortalaması yanıltıcı.** Tipik bir araç (medyan) DQL'de 693 s, `dql_safe`'te 671 s ile
   neredeyse aynı sürede geçiyor. DQL'in ortalamasını yükselten, ajanların eğitim süresinin dışında
   kilitlendiği dönemde (Bölüm 5) çok uzun bekleyen araçlar.
2. **`dql_safe`'in kazancı "daha iyi öğrenme" değil.** Aynı modellerin üstüne eklenen kural tabanlı
   bir güvenlik katmanı, bu kilitlenmeyi engelliyor. Kazancın neredeyse tamamı "azami kırmızı"
   kuralından geliyor (Bölüm 6).

## 2. Ölçüm adil mi?

Evet. Tüm modlar aynı koşullarda ölçüldü:

| Koşul | Durum |
|---|---|
| Ağ | Aynı (`yeni_normal_sure.net.xml`). Yeşil dalga modlarında yalnızca 10 kavşağın faz süreleri ve ofsetleri değişik bir kopya. |
| Arka plan trafiği | Aynı talep dosyası (`arac_talepleri/deneme_1.rou.xml`) |
| Test araçları | Aynı 100 araç, aynı planlanan kalkış zamanları (sabit tohum 42) |
| Rastgelelik | Her mod aynı 5 SUMO tohumuyla (1–5) koşturuldu |
| Tamamlanma | 25 koşunun hepsinde 100/100 araç vardı; eksik araç yok |
| Süre sınırı | Hiçbir koşu süre sınırına takılmadı; hepsi "tüm test araçları vardı" koşuluyla 16700–19300 s arasında bitti |
| Modeller | Eğitilmiş `.pth` dosyaları değiştirilmedi, yeniden eğitim yapılmadı (MD5 ile doğrulandı) |

Tüm araçlar vardığı için ortalamalar "sadece varanlar" yanlılığı taşımıyor. Eski Tablo 4'te DQL
94/100'dü ve ortalamaya en uzun süren 6 araç girmemişti.

## 3. Ne yapıldı

1. **Teşhis çıktıları.** Ölçüm betiğine SUMO tripinfo, istatistik ve log çıktıları eklendi. Her araç için
   planlanan kalkış, giriş gecikmesi ve toplam süre kaydediliyor. Varamayan araçlar "girmedi / takıldı"
   olarak sınıflandırılıyor (bu ölçümde hiç çıkmadı).
2. **Bugünkü dosyalarla yeniden ölçüm.** Tablo 4, 17 Mayıs'taki dosyalarla üretilmişti. Sonrasında ağ,
   talep ve 10 modelin 7'si değişti. Eski CSV'ler `sonuclar/eski_tablo4_17mayis/` altında saklandı.
3. **Yeşil dalga ofset hatası düzeltildi (`green_wave_fixed`).** Kodda ofsetin işareti tersti.
   SUMO'da faz 0'ın tam ofset saniyesinde başladığı TraCI ile doğrulandı (`sonuclar/ofset_dogrulama.csv`).
   Eski mod karşılaştırma için aynen duruyor.
4. **DQL güvenlik katmanı (`dql_safe`).** Aynı modeller, yeniden eğitim yok. İki kural var:
   - Doğru sarı geçiş: faz değişiminde yeşilden kırmızıya dönen her bağlantı 5 s sarı yanıyor.
     Ağdaki sarı fazlar yalnızca döngüdeki bir sonraki faza göre tasarlanmıştı. Ajan fazları serbest
     sırayla seçince bazı bağlantılar sarısız kırmızıya geçiyordu.
   - Azami kırmızı: bir bağlantı 90 s'dir kırmızıysa ve onu kullanmak için bekleyen araç varsa,
     model kararı yerine o bağlantıya yeşil veren eylem seçiliyor.
5. **5 tohum.** Her mod 5 farklı SUMO tohumuyla koşturuldu, sonuçlar ortalandı.
6. **Teşhis koşuları.** DQL'deki uzun süreleri açıklamak için ek koşular yapıldı (Bölüm 5 ve 6).

## 4. Giriş kuyruğu (tüm modlarda aynı)

Test araçları planlanan zamanda ağa giremiyor; girişte ortalama **~2200 s (36,6 dk)** bekliyorlar.
Bu bekleme beş modda da aynı:

| Mod | Giriş beklemesi | Toplam (bekleme + koridor) |
|---|---|---|
| Varsayılan | 2199 s | 3453 s (57,5 dk) |
| Yeşil dalga (rapordaki) | 2201 s | 3440 s (57,3 dk) |
| Yeşil dalga (düzeltilmiş) | 2198 s | 3297 s (55,0 dk) |
| DQL | 2198 s | 3238 s (54,0 dk) |
| DQL + güvenlik | 2198 s | 2875 s (47,9 dk) |

Sebep ışıklar değil, talep dosyası. Akışlarda `departLane` tanımlı olmadığı için SUMO tüm araçları
girişteki ilk şeritten, durarak sokuyor. Zirvede (3000–7000 s) saniyede 0,65 araç tek şeritten
sokulamıyor. Talep dosyası değiştirilemeyecek dosyalardan olduğu için dokunulmadı. Bu yüzden
modları karşılaştırmak için "koridorda geçen süre" kullanılmalı. "Toplam" ise aracın gerçek
yolculuk süresini gösterir.

## 5. DQL neden bazen çok yavaş?

Araçları ağa giriş zamanına göre ayırınca (5 tohum, ortalama koridor süresi):

| Mod | 0–12000 s arasında girenler (n≈354) | 12000 s sonrası girenler (n≈146) |
|---|---|---|
| Varsayılan | 1150 s | 1507 s |
| Yeşil dalga (rapordaki) | 1092 s | 1598 s |
| Yeşil dalga (düzeltilmiş) | 1071 s | 1168 s |
| DQL | 789 s | **1653 s** (en kötü 96 dk) |
| DQL + güvenlik | 693 s | 640 s |

DQL'de 12000 s'den sonra girenler çok yavaş. Seed 4'te araçların nerede durduğu kaydedildi:

| Giriş zamanı | DQL koridor süresi | Bunun Turgut Özal kavşağında beklenen kısmı |
|---|---|---|
| 0–12000 s | ~600 s | ~13 s |
| 12000–15000 s | 4102 s | **3143 s (52 dk)** |

Sebep:

- Ajanlar `TOTAL_STEPS = 12000` ile, yani her bölüm 12000 s'de bitecek şekilde eğitildi. Talepteki
  akışlar da 12000 s'de bitiyor.
- Ama giriş kuyruğu yüzünden trafik ~17000 s'ye kadar sürüyor. "Talep bitti, kuyruk boşalıyor"
  durumu ajanların eğitimde hiç görmediği bir durum.
- Turgut Özal'da koridor yönü yalnızca faz 0'da yeşil yanıyor. Bu dönemde ajan faz 0'ı neredeyse
  hiç seçmiyor ve koridor araçları ortalama 52 dk kırmızıda bekliyor.

Not: Yukarıdaki "0–12000 s" sütunu bir analiz kesitidir, ana sonuç değildir. Raporun ana tablosu
Bölüm 1'deki, tüm araçları kapsayan tablodur. Bu kesit, DQL'in eğitildiği koşullarda ne kadar iyi
olduğunu göstermek için kullanılabilir: ilk 12000 s'de DQL varsayılandan %31 hızlı.

## 6. Güvenlik katmanının hangi parçası işe yarıyor?

Yalnızca sarı düzeltmesi açık, azami kırmızı kapalı bir varyant 5 tohumla koşturuldu:

| | Ort. koridor süresi | Acil duruş / koşu | Işınlanma / koşu |
|---|---|---|---|
| DQL | 1040 s | 82 | 187 |
| Sadece sarı düzeltmesi | 907–1679 s (ort. 1229 s) | ~0 | ~200 |
| Sarı + azami kırmızı (`dql_safe`) | 677 s | 0 | 0 |

- **Sarı düzeltmesi** acil duruşları sıfırlıyor, ama süreyi iyileştirmiyor.
- **Azami kırmızı kuralı** Turgut Özal'daki kilitlenmeyi ve Yeşilyurt AVM yan yolundaki (E70)
  açlığı kırıyor. Süredeki kazanç ve ışınlanmaların sıfırlanması bundan geliyor.
- Güvenlik katmanı koşu başına ~885 kez model kararını değiştiriyor (10 kavşak toplamı,
  kararların kabaca %5'i).

## 7. Güvenlik göstergeleri (koşu başına ortalama)

| Mod | Işınlanma | Acil duruş | Sarısız yeşil→kırmızı geçiş |
|---|---|---|---|
| Varsayılan | 0 | 0 | 0 |
| Yeşil dalga (rapordaki) | 0 | 0 | 0 |
| Yeşil dalga (düzeltilmiş) | 0 | 0,2 | 0 |
| DQL | 187 | 82 | 2686 |
| DQL + güvenlik | 0 | 0 | 0 |

## 8. Eski Tablo 4 ile karşılaştırma

| Mod | Tablo 4 (17 Mayıs, tek tohum) | Bugün (5 tohum ort.) |
|---|---|---|
| Varsayılan | 1336 s, 100/100 | 1254 s, 500/500 |
| Yeşil dalga | 1322 s, 100/100 | 1240 s, 500/500 |
| DQL | 1071 s, 94/100 | 1040 s, 500/500 |

Fark nedenleri: 17 Mayıs sonrası değişen ağ, talep ve modeller; Tablo 4'ün tek tohum olması
(aynı modda tohumlar arası fark 100–270 s); DQL'de varamayan 6 aracın ortalamaya girmemiş olması.

## 9. Rapor için öneriler

- Tablo 4'ü Bölüm 1'deki tabloyla değiştirin; tohum sayısını ve ± sapmayı belirtin.
- Yeşil dalga için düzeltilmiş ofsetli sonucu (1099 s) kullanın, ofset hatasını yöntemde not edin.
- DQL için iki satır verin: saf DQL (1040 s) ve DQL + güvenlik katmanı (677 s). Güvenlik katmanının
  kural tabanlı olduğunu ve kararların ~%5'ine müdahale ettiğini açıkça yazın.
- DQL'in 12000 s sonrasındaki kilitlenmesini bir sınırlama olarak yazın. Kalıcı çözüm, ajanları
  talep bittikten sonraki dönemi de kapsayan daha uzun bölümlerle yeniden eğitmektir (bu çalışmada
  yapılmadı).
- Giriş kuyruğu beklemesinin (~37 dk) ışıklardan bağımsız olduğunu ve karşılaştırmada koridor
  süresinin kullanıldığını belirtin.

## 10. Dosyalar

| Dosya | İçerik |
|---|---|
| `sonuclar/OZET.md` | Betiğin ürettiği sayısal özet (her güncellemede yenilenir) |
| `sonuclar/karsilastirma_coklu_tohum.csv` | Mod başına ortalama ± standart sapma |
| `sonuclar/karsilastirma_ozet.csv` | Koşu (mod × tohum) bazında tüm metrikler |
| `sonuclar/{mod}_s{tohum}_travel_times.csv` | Araç bazında süreler |
| `sonuclar/eski_tablo4_17mayis/` | Rapordaki Tablo 4'ün kaynak CSV'leri |
| `README.md` | Modlar, bayraklar, çalıştırma ve metrik tanımları |

Bölüm 5'teki kavşak bazında bekleme ve Bölüm 6'daki "sadece sarı düzeltmesi" sonuçları ayrı teşhis
koşularından alındı; bu koşuların ham çıktıları repoda değildir.
