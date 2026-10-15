# RL-traffic-signal-control

Samsun Batipark - Engiz koridorundaki 10 sinyalize kavsagin trafik isiklarinin
SUMO simulasyonu ve Derin Q-Ogrenme (DQL) ile kontrolu.

Her kavsak icin ayri bir DQL ajani egitilir (durum: detector kuyruklari + aktif faz,
odul: kavsaktaki toplam bekleme suresi). Egitilen ajanlar daha sonra koridor
boyunca birlikte calistirilir ve sabit sureli program ile yesil dalgaya gore
karsilastirilir.

## Klasor yapisi

| Yol | Icerik |
|---|---|
| `yeni_normal_sure.net.xml`, `yeni_normal_sure.sumocfg` | Ana SUMO agi ve konfigurasyonu (modeller bu agla egitildi) |
| `arac_talepleri/deneme_1.rou.xml` | Egitim ve olcumde kullanilan arac talebi (flow'lar) |
| `Detectors/detector_deneme.add.xml` | Ajanlarin durum olarak okudugu E2 (lanearea) detector'leri |
| `DQL_bekleme_suresi/` | Bekleme suresi odullu DQL egitimi. `kavsak_configleri.py` kavsak tanimlari, `train_*.py` egitim betikleri, `kavsaklar/<kavsak>/` egitilmis modeller (`dql_bekleme_suresi_model.pth`) ve egitim grafikleri |
| `koridor_olcumleri/` | Koridor seyahat suresi olcumu (varsayilan, yesil dalga, DQL). Ayrinti: [koridor_olcumleri/README.md](koridor_olcumleri/README.md) |
| `DQL_koridor/` | Yeni yontem: kalkanli, cok metrikli, koridor farkindalikli DQN (10 ajan birlikte, devam ettirilebilir egitim). Ayrinti: [DQL_koridor/README.md](DQL_koridor/README.md) |
| `DQL_kuyruk_uzunlugu/`, `QL/`, `main.py`, `agent.py` | Onceki denemeler (kuyruk odullu DQL, tablo Q-ogrenme) |
| `normal_sonuclar/`, `yesil_dalga_sonuclar/` | Eski olcum ciktilari |
| `rapor_kaynaklari/` | Rapor belgeleri |

## Gereksinimler

- Eclipse SUMO 1.26.0 (gelistirme ortami). Baska surumlerde sayilar biraz farkli cikabilir.
- Python 3.13 ve `requirements.txt` icindeki paketler:

```powershell
pip install -r requirements.txt
```

PyTorch icin GPU kullanilacaksa uygun CUDA surumu https://pytorch.org adresinden secilmelidir;
CPU surumu da yeterlidir.

## SUMO_HOME

Betikler `traci` ve `sumolib`'i `%SUMO_HOME%\tools` altindan yukler. `SUMO_HOME`
tanimli degilse betikler hata verip cikar.

```powershell
# Sadece bu oturum icin
$env:SUMO_HOME = "D:\Sumo"
# Kalici (yeni terminal acmak gerekir)
setx SUMO_HOME "D:\Sumo"
```

`sumo` ve `sumo-gui` komutlarinin PATH'te olmasi gerekir (`%SUMO_HOME%\bin`).

Not: Anaconda ortaminda `torch` `numpy`'dan once import edilirse `OMP: Error #15`
hatasi alinabilir. Betikler `numpy`'yi once yukler.

## Hizli baslangic

```powershell
# Koridor olcumu: rapordaki uc mod, tek tohum
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode all --seed 1

# Bes mod, uc tohum, 4 paralel surec
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode hepsi --seeds 1 2 3 --max-steps 36000 --jobs 4
```

Tek bir kavsagin modelini egitmek (modelleri degistirir, dikkat):

```powershell
python DQL_bekleme_suresi\train_turkis_kavsak.py
```
