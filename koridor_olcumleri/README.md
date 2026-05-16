# Koridor Seyahat Suresi Olcumu

Bu klasor, `-4841` edge'inden `-4779.656.62.62` edge'ine giden 100 test aracinin
seyahat suresini olcmek icindir.

Ana dosyalar:

- `koridor_seyahat_suresi_olcumu.py`: default, green-wave ve DQL modlarini calistirir.
- `test_araclari.rou.xml`: sabit seed ile uretilen 100 test araci.
- `default_koridor.sumocfg`: orijinal ag + mevcut trafik + test araclari.
- `green_wave_koridor.sumocfg`: green-wave ag kopyasi + mevcut trafik + test araclari.
- `dql_koridor.sumocfg`: orijinal ag + mevcut trafik + test araclari + DQL kontrol.
- `green_wave_offsetleri.csv`: 80 km/h ve 120 sn ortak cevrim icin offset tablosu.

Kullanım:

```powershell
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --prepare-only
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode default
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode green_wave
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode dql
python koridor_olcumleri\koridor_seyahat_suresi_olcumu.py --mode all
```

Sonuclar `koridor_olcumleri/sonuclar` altina yazilir.
