import os
import sys
import traci
import numpy as np
import xml.etree.ElementTree as ET

# agent.py dosyasından DQNAgent sınıfını içeri aktarıyoruz
from agent import DQNAgent

# 1. SUMO Ortam Değişkeni Kontrolü
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Lütfen 'SUMO_HOME' ortam değişkenini tanımlayın!")

# --- EĞİTİM AYARLARI ---
EPISODE_SAYISI = 15  # Kalıcı eğitim için yüksek tutuldu
MAX_ADIM = 3600      # 1 saatlik simülasyon (saniye)

KAVSAK_ISIMLERI = [
    "ballica_kavsak", "ifam_kavsak", "taflan_un_kavsak", "adnan_menderes_kavsak", 
    "polis_okulu_kavsak", "uluskent_kavsak", "beyaz_saray_kavsak", "turgut_ozal_kavsak", 
    "korfez_kavsak", "pelitkoy_kavsak", "yenimahalle_kavsak", "atakent_kavsak", 
    "omurevleri_kavsak", "turkis_kavsak", "mimar_sinan_kavsak", "yesilyurt_avm_kavsak", 
    "atakum_lisesi_kavsak"
] 

# Ajanları ve kavşak bilgilerini tutacağımız sözlükler
kavsak_ajanlari = {}
kavsak_seritleri = {}
kavsak_yesil_fazlari = {} 
kavsak_toplam_faz_sayisi = {} # YENİ: Çökme önleyici sınır

def kavsaklari_ve_ajanlari_baslat():
    """TraCI açıldığında her kavşak için şerit sayılarını ve fazları otomatik bulur, ajanları yaratır."""
    global kavsak_ajanlari, kavsak_seritleri, kavsak_yesil_fazlari, kavsak_toplam_faz_sayisi
    
    for kavsak_id in KAVSAK_ISIMLERI:
        try:
            # Kavşağa bağlı şeritleri bul (Tekrarları set ile temizliyoruz)
            seritler = list(set(traci.trafficlight.getControlledLanes(kavsak_id)))
            kavsak_seritleri[kavsak_id] = seritler
            durum_boyutu = len(seritler)
            
            tum_fazlar = traci.trafficlight.getCompleteRedYellowGreenDefinition(kavsak_id)[0].phases
            kavsak_toplam_faz_sayisi[kavsak_id] = len(tum_fazlar) # Toplam limiti kaydet
            
            # YENİ FİLTRE: İçinde 'y' veya 'Y' (Sarı) olan fazları kesinlikle ana yeşil kabul etme!
            yesil_fazlar = [i for i, faz in enumerate(tum_fazlar) if ('G' in faz.state or 'g' in faz.state) and ('y' not in faz.state and 'Y' not in faz.state)]
            kavsak_yesil_fazlari[kavsak_id] = yesil_fazlar
            
            faz_sayisi = len(yesil_fazlar)
            
            if kavsak_id not in kavsak_ajanlari:
                yeni_ajan = DQNAgent(input_size=durum_boyutu, output_size=faz_sayisi)
                yeni_ajan.load_model(kavsak_id)
                kavsak_ajanlari[kavsak_id] = yeni_ajan
                print(f"[{kavsak_id}] Ajanı Başlatıldı! (Şerit: {durum_boyutu}, Kesin Yeşil Faz: {faz_sayisi})")
                
        except Exception as e:
            print(f"HATA: {kavsak_id} kavşağı bulunamadı! Netedit ismini kontrol et. Detay: {e}")

def durumu_al(kavsak_id):
    """Kavşağa bağlı şeritlerdeki TÜM araçların (duran ve hareket eden) sayısını dizi olarak döndürür."""
    durum = []
    for serit in kavsak_seritleri[kavsak_id]:
        kuyruk = traci.lane.getLastStepVehicleNumber(serit)
        durum.append(kuyruk)
    return np.array(durum)

def odul_hesapla(kavsak_id):
    """Ödül Fonksiyonu: Kuyruk ne kadar uzunsa, o kadar negatif ödül (ceza) alır."""
    toplam_kuyruk = sum(durumu_al(kavsak_id))
    return -toplam_kuyruk 

def egitimi_baslat():
    print(f"--- DQL EĞİTİMİ BAŞLIYOR ({EPISODE_SAYISI} Bölüm) ---")
    
    # Hızlı eğitim için arayüzsüz mod. İzlemek istersen "sumo" yerine "sumo-gui" yapabilirsin.
    sumoCmd = ["sumo-gui", "-c", "yeni_normal_sure.sumocfg", "--random"]
    
    for e in range(EPISODE_SAYISI):
        print(f"\n>> Episode {e+1}/{EPISODE_SAYISI} Başladı...")
        traci.start(sumoCmd)
        
        if e == 0:
            kavsaklari_ve_ajanlari_baslat()
            
        adim = 0
        while traci.simulation.getMinExpectedNumber() > 0 and adim < MAX_ADIM:
            
            # Her 5 saniyede bir Karar Zamanı
            if adim % 5 == 0:
                degisecek_kavsaklar = {} 
                
                for kavsak_id in KAVSAK_ISIMLERI:
                    if kavsak_id not in kavsak_ajanlari: continue
                    ajan = kavsak_ajanlari[kavsak_id]
                    
                    mevcut_durum = durumu_al(kavsak_id)
                    mevcut_faz = traci.trafficlight.getPhase(kavsak_id)
                    
                    secilen_aksiyon = ajan.act(mevcut_durum)
                    hedef_yesil_faz = kavsak_yesil_fazlari[kavsak_id][secilen_aksiyon]
                    
                    # YENİ: Modulo (%) ile matematiksel kalkan eklendi (Örn: (3+1) % 4 = 0)
                    if mevcut_faz != hedef_yesil_faz and mevcut_faz in kavsak_yesil_fazlari[kavsak_id]:
                        sari_faz = (mevcut_faz + 1) % kavsak_toplam_faz_sayisi[kavsak_id]
                        traci.trafficlight.setPhase(kavsak_id, sari_faz)
                        degisecek_kavsaklar[kavsak_id] = hedef_yesil_faz 
                    else:
                        traci.trafficlight.setPhase(kavsak_id, hedef_yesil_faz)
                        
                    odul = odul_hesapla(kavsak_id)
                    yeni_durum = durumu_al(kavsak_id)
                    done = adim >= MAX_ADIM
                    ajan.memory.add(mevcut_durum, secilen_aksiyon, odul, yeni_durum, done)
                    ajan.replay()

                # --- 3 SANİYE SARI IŞIK BEKLETME SİSTEMİ ---
                if len(degisecek_kavsaklar) > 0:
                    for _ in range(3):
                        traci.simulationStep()
                        adim += 1
                        
                    for k_id, h_faz in degisecek_kavsaklar.items():
                        traci.trafficlight.setPhase(k_id, h_faz)
                        
                    for _ in range(2):
                        traci.simulationStep()
                        adim += 1
                    continue 

            traci.simulationStep()
            adim += 1

        traci.close()
        
        # BÖLÜM SONU İŞLEMLERİ
        ornek_epsilon = 0
        for kavsak_id, ajan in kavsak_ajanlari.items():
            ajan.update_epsilon()         
            ajan.save_model(kavsak_id)    
            ornek_epsilon = ajan.epsilon  
            
        print(f"Episode {e+1} Bitti. Modeller Kaydedildi! Yeni Keşfetme Oranı: {ornek_epsilon:.3f}")

if __name__ == "__main__":
    egitimi_baslat()