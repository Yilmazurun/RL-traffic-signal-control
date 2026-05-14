# ============================================
# IMPORTS
# ============================================

import argparse
import csv
import os
import sys

# ============================================
# SUMO PATH
# ============================================

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    sys.exit("SUMO_HOME environment variable is not defined")

import traci

# ============================================
# SUMO CONFIG
# ============================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = (
    SCRIPT_DIR
    if os.path.exists(os.path.join(SCRIPT_DIR, "yeni_normal_sure.sumocfg"))
    else os.path.dirname(SCRIPT_DIR)
)
OUTPUT_DIR = SCRIPT_DIR

USE_GUI = False
SUMO_BINARY = "sumo-gui" if USE_GUI else "sumo"
SUMO_CONFIG_FILE = os.path.join(PROJECT_ROOT, "yeni_normal_sure.sumocfg")

# ============================================
# GENERAL SETTINGS
# ============================================

TLS_ID = "turkis_kavsak"

NUM_EPISODES = 3
TOTAL_STEPS = 12000
MEASURE_INTERVAL = 10

DETAIL_CSV_FILE = os.path.join(OUTPUT_DIR, "default_sure_bekleme_suresi_detay.csv")
SUMMARY_CSV_FILE = os.path.join(OUTPUT_DIR, "default_sure_bekleme_suresi_ozet.csv")

DETAIL_FIELDS = [
    "episode",
    "time",
    "phase",
    "phase_name",
    "active_vehicle_count",
    "total_waiting_time",
    "average_waiting_time_per_vehicle",
    "max_vehicle_waiting_time",
]

SUMMARY_FIELDS = [
    "episode",
    "total_steps",
    "measure_interval",
    "average_total_waiting_time",
    "average_waiting_time_per_vehicle",
    "max_total_waiting_time",
    "max_vehicle_waiting_time",
    "cumulative_total_waiting_time",
    "measurement_count",
]

PHASE_NAMES = {
    0: "MAIN_GREEN",
    1: "MAIN_YELLOW",
    2: "TURN_GREEN",
    3: "TURN_YELLOW",
    4: "SIDE_GREEN",
    5: "SIDE_YELLOW",
}

# ============================================
# SUMO HELPER FUNCTIONS
# ============================================


# Trafik isiginin mevcut phase indexini dondurur.
def get_current_phase():
    return traci.trafficlight.getPhase(TLS_ID)


# Aktif araclarin bekleme surelerini okur.
def get_waiting_time_snapshot():
    vehicle_ids = traci.vehicle.getIDList()
    active_vehicle_count = len(vehicle_ids)
    total_waiting_time = 0.0
    max_vehicle_waiting_time = 0.0

    for vehicle_id in vehicle_ids:
        waiting_time = traci.vehicle.getWaitingTime(vehicle_id)
        total_waiting_time += waiting_time
        max_vehicle_waiting_time = max(max_vehicle_waiting_time, waiting_time)

    average_waiting_time_per_vehicle = total_waiting_time / max(active_vehicle_count, 1)

    return (
        active_vehicle_count,
        total_waiting_time,
        average_waiting_time_per_vehicle,
        max_vehicle_waiting_time,
    )


# SUMO'yu bir episode icin baslatir.
# Burada trafik isigina hic mudahale edilmez; net dosyasindaki default sureler calisir.
def start_sumo_for_episode(episode_number):
    sumo_config = [
        SUMO_BINARY,
        "-c",
        SUMO_CONFIG_FILE,
        "--step-length",
        "1",
        "--lateral-resolution",
        "0",
        "--seed",
        str(episode_number + 1),
    ]

    if USE_GUI:
        sumo_config += ["--delay", "50"]

    traci.start(sumo_config)

    if USE_GUI:
        try:
            traci.gui.setSchema("View #0", "real world")
        except Exception:
            pass


# ============================================
# CSV FUNCTIONS
# ============================================


# CSV dosyasini basliklariyla sifirdan olusturur.
def create_csv(file_path, fieldnames):
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


# Tek bir satiri ilgili CSV dosyasina ekler.
def append_csv(file_path, fieldnames, row):
    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(row)


# Birden fazla satiri ilgili CSV dosyasina tek seferde ekler.
def append_csv_rows(file_path, fieldnames, rows):
    if not rows:
        return

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerows(rows)


# ============================================
# MEASUREMENT LOOP
# ============================================


# Default surelerle calisan agi izler ve bekleme suresi metriklerini CSV'ye yazar.
def measure_default_waiting_times(num_episodes, total_steps, measure_interval):
    create_csv(DETAIL_CSV_FILE, DETAIL_FIELDS)
    create_csv(SUMMARY_CSV_FILE, SUMMARY_FIELDS)

    print("\n=== DEFAULT SURE BEKLEME SURESI OLCUMU BASLADI ===")
    print("Trafik isigina mudahale edilmiyor; agdaki sureler aynen kullaniliyor.")

    for episode in range(1, num_episodes + 1):
        print(f"\n========== EPISODE {episode}/{num_episodes} ==========")

        start_sumo_for_episode(episode - 1)

        total_waiting_time_sum = 0.0
        average_vehicle_waiting_time_sum = 0.0
        max_total_waiting_time = 0.0
        max_vehicle_waiting_time_for_episode = 0.0
        measurement_count = 0
        detail_rows = []

        try:
            while traci.simulation.getTime() < total_steps:
                traci.simulationStep()
                current_time = int(traci.simulation.getTime())

                if current_time % measure_interval != 0:
                    continue

                (
                    active_vehicle_count,
                    total_waiting_time,
                    average_waiting_time_per_vehicle,
                    max_vehicle_waiting_time,
                ) = get_waiting_time_snapshot()

                phase = get_current_phase()

                detail_rows.append(
                    {
                        "episode": episode,
                        "time": current_time,
                        "phase": phase,
                        "phase_name": PHASE_NAMES.get(phase, "UNKNOWN"),
                        "active_vehicle_count": active_vehicle_count,
                        "total_waiting_time": total_waiting_time,
                        "average_waiting_time_per_vehicle": average_waiting_time_per_vehicle,
                        "max_vehicle_waiting_time": max_vehicle_waiting_time,
                    }
                )

                total_waiting_time_sum += total_waiting_time
                average_vehicle_waiting_time_sum += average_waiting_time_per_vehicle
                max_total_waiting_time = max(max_total_waiting_time, total_waiting_time)
                max_vehicle_waiting_time_for_episode = max(
                    max_vehicle_waiting_time_for_episode,
                    max_vehicle_waiting_time,
                )
                measurement_count += 1

                if measurement_count % 50 == 0:
                    print(
                        f"Episode: {episode}, "
                        f"Time: {current_time}, "
                        f"Phase: {PHASE_NAMES.get(phase, 'UNKNOWN')}, "
                        f"Total Waiting Time: {total_waiting_time:.2f}, "
                        f"Avg Vehicle Waiting: {average_waiting_time_per_vehicle:.2f}"
                    )

        finally:
            traci.close()

        average_total_waiting_time = total_waiting_time_sum / max(measurement_count, 1)
        average_waiting_time_per_vehicle = average_vehicle_waiting_time_sum / max(
            measurement_count,
            1,
        )

        append_csv_rows(DETAIL_CSV_FILE, DETAIL_FIELDS, detail_rows)

        append_csv(
            SUMMARY_CSV_FILE,
            SUMMARY_FIELDS,
            {
                "episode": episode,
                "total_steps": total_steps,
                "measure_interval": measure_interval,
                "average_total_waiting_time": average_total_waiting_time,
                "average_waiting_time_per_vehicle": average_waiting_time_per_vehicle,
                "max_total_waiting_time": max_total_waiting_time,
                "max_vehicle_waiting_time": max_vehicle_waiting_time_for_episode,
                "cumulative_total_waiting_time": total_waiting_time_sum,
                "measurement_count": measurement_count,
            },
        )

        print(
            f"\nEpisode {episode} bitti. "
            f"Average Total Waiting Time: {average_total_waiting_time:.2f}, "
            f"Average Vehicle Waiting: {average_waiting_time_per_vehicle:.2f}, "
            f"Max Total Waiting Time: {max_total_waiting_time:.2f}"
        )

    print(f"\nDetay CSV kaydedildi: {DETAIL_CSV_FILE}")
    print(f"Ozet CSV kaydedildi: {SUMMARY_CSV_FILE}")


# Komut satiri parametrelerini okur.
def parse_args():
    parser = argparse.ArgumentParser(
        description="Yeni normal sure agi icin default bekleme suresi olcumu"
    )
    parser.add_argument("--episodes", type=int, default=NUM_EPISODES)
    parser.add_argument("--steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--interval", type=int, default=MEASURE_INTERVAL)
    parser.add_argument("--gui", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.gui:
        USE_GUI = True
        SUMO_BINARY = "sumo-gui"

    measure_default_waiting_times(
        num_episodes=args.episodes,
        total_steps=args.steps,
        measure_interval=args.interval,
    )
