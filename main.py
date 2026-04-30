import os
import sys
import traci
import xml.etree.ElementTree as ET

# 1. SUMO Ortam Değişkeni Kontrolü
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Lütfen 'SUMO_HOME' ortam değişkenini tanımlayın!")

def simulasyonu_calistir():
    print("Simülasyon başlatılıyor...")
    
    
    # Araç gidişini izlemek için "sumo" yerine "sumo-gui" yaz
    sumoCmd = ["sumo", "-c", "yesil_dalga.sumocfg", "--random"] 
    
    traci.start(sumoCmd)
    
    # Simülasyonu sistemdeki tüm araçlar bitene kadar çalıştır
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulation.step()
        
    traci.close()
    print("Simülasyon tamamlandı! Veriler analiz ediliyor...\n")

def verileri_analiz_et():
    # SUMO'nun oluşturduğu dosyayı oku
    try:
        tree = ET.parse("yesil_dalga_sonuclari6.xml")
        root = tree.getroot()
    except FileNotFoundError:
        print("Hata: sefer_sonuclari.xml dosyası bulunamadı. Simülasyon düzgün çalışmadı.")
        return

    toplam_arac = 0
    toplam_sefer_suresi = 0.0 # duration
    toplam_bekleme_suresi = 0.0 # waitingTime
    
    # XML içindeki her bir 'tripinfo' etiketini gez
    for trip in root.findall('tripinfo'):
        toplam_arac += 1
        
        #float olmasına dikkat
        toplam_sefer_suresi += float(trip.get('duration'))
        toplam_bekleme_suresi += float(trip.get('waitingTime'))
        
    if toplam_arac > 0:
        ortalama_sefer = toplam_sefer_suresi / toplam_arac
        ortalama_bekleme = toplam_bekleme_suresi / toplam_arac
        
        print(f"--- SİMÜLASYON SONUÇLARI ---")
        print(f"Hedefe Ulaşan Toplam Araç: {toplam_arac}")
        print(f"Ortalama Sefer Süresi: {ortalama_sefer:.2f} saniye")
        print(f"Ortalama Bekleme Süresi: {ortalama_bekleme:.2f} saniye")
    else:
        print("Simülasyonda rotasını tamamlayan araç bulunamadı.")



if __name__ == "__main__":
    simulasyonu_calistir()
    verileri_analiz_et()