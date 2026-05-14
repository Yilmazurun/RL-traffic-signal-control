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

NUM_EPISODES = 1
TOTAL_STEPS = 12000
MEASURE_INTERVAL = 10

DETAIL_CSV_FILE = os.path.join(OUTPUT_DIR, "default_sure_kuyruk_detay.csv")
SUMMARY_CSV_FILE = os.path.join(OUTPUT_DIR, "default_sure_kuyruk_ozet.csv")

# ============================================
# DETECTORS
# ============================================

MAIN_DETECTORS = [
    "turkis_b_e_0",
    "turkis_b_e_1",
    "turkis_e_b_0",
    "turkis_e_b_1",
    "turkis_e_b_2",
]

TURN_DETECTORS = [
    "turkis_b_e_2",
]

SIDE_DETECTORS = [
    "turkis_0",
    "turkis_1",
    "turkis_2",
]

ALL_DETECTORS = MAIN_DETECTORS + TURN_DETECTORS + SIDE_DETECTORS

DETAIL_FIELDS = [
    "episode",
    "time",
    "phase",
    "phase_name",
    "main_queue",
    "turn_queue",
    "side_queue",
    "total_queue",
]

SUMMARY_FIELDS = [
    "episode",
    "total_steps",
    "measure_interval",
    "average_main_queue",
    "average_turn_queue",
    "average_side_queue",
    "average_queue",
    "max_queue",
    "min_queue",
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


# Verilen lane area detector icindeki arac sayisini dondurur.
def get_queue_length(detector_id):
    return traci.lanearea.getLastStepVehicleNumber(detector_id)


# Verilen detector listesindeki toplam arac sayisini hesaplar.
def get_queue_sum(detectors):
    total = 0

    for detector_id in detectors:
        total += get_queue_length(detector_id)

    return total


# O anki detector kuyruklarini grup bazinda okur.
def get_queue_snapshot():
    main_queue = get_queue_sum(MAIN_DETECTORS)
    turn_queue = get_queue_sum(TURN_DETECTORS)
    side_queue = get_queue_sum(SIDE_DETECTORS)
    total_queue = main_queue + turn_queue + side_queue

    return main_queue, turn_queue, side_queue, total_queue


# Trafik isiginin mevcut phase indexini dondurur.
def get_current_phase():
    return traci.trafficlight.getPhase(TLS_ID)


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


# Default surelerle calisan agi izler ve kuyruk metriklerini CSV'ye yazar.
def measure_default_queues(num_episodes, total_steps, measure_interval):
    create_csv(DETAIL_CSV_FILE, DETAIL_FIELDS)
    create_csv(SUMMARY_CSV_FILE, SUMMARY_FIELDS)

    print("\n=== DEFAULT SURE KUYRUK OLCUMU BASLADI ===")
    print("Trafik isigina mudahale edilmiyor; agdaki sureler aynen kullaniliyor.")

    for episode in range(1, num_episodes + 1):
        print(f"\n========== EPISODE {episode}/{num_episodes} ==========")

        start_sumo_for_episode(episode - 1)

        main_queue_sum = 0.0
        turn_queue_sum = 0.0
        side_queue_sum = 0.0
        total_queue_sum = 0.0
        max_queue = None
        min_queue = None
        measurement_count = 0
        detail_rows = []

        try:
            while traci.simulation.getTime() < total_steps:
                traci.simulationStep()
                current_time = int(traci.simulation.getTime())

                if current_time % measure_interval != 0:
                    continue

                main_queue, turn_queue, side_queue, total_queue = get_queue_snapshot()
                phase = get_current_phase()

                detail_rows.append(
                    {
                        "episode": episode,
                        "time": current_time,
                        "phase": phase,
                        "phase_name": PHASE_NAMES.get(phase, "UNKNOWN"),
                        "main_queue": main_queue,
                        "turn_queue": turn_queue,
                        "side_queue": side_queue,
                        "total_queue": total_queue,
                    }
                )

                main_queue_sum += main_queue
                turn_queue_sum += turn_queue
                side_queue_sum += side_queue
                total_queue_sum += total_queue
                max_queue = total_queue if max_queue is None else max(max_queue, total_queue)
                min_queue = total_queue if min_queue is None else min(min_queue, total_queue)
                measurement_count += 1

                if measurement_count % 50 == 0:
                    print(
                        f"Episode: {episode}, "
                        f"Time: {current_time}, "
                        f"Phase: {PHASE_NAMES.get(phase, 'UNKNOWN')}, "
                        f"Queue: {total_queue}"
                    )

        finally:
            traci.close()

        average_main_queue = main_queue_sum / max(measurement_count, 1)
        average_turn_queue = turn_queue_sum / max(measurement_count, 1)
        average_side_queue = side_queue_sum / max(measurement_count, 1)
        average_queue = total_queue_sum / max(measurement_count, 1)

        append_csv_rows(DETAIL_CSV_FILE, DETAIL_FIELDS, detail_rows)

        append_csv(
            SUMMARY_CSV_FILE,
            SUMMARY_FIELDS,
            {
                "episode": episode,
                "total_steps": total_steps,
                "measure_interval": measure_interval,
                "average_main_queue": average_main_queue,
                "average_turn_queue": average_turn_queue,
                "average_side_queue": average_side_queue,
                "average_queue": average_queue,
                "max_queue": max_queue if max_queue is not None else 0,
                "min_queue": min_queue if min_queue is not None else 0,
                "measurement_count": measurement_count,
            },
        )

        print(
            f"\nEpisode {episode} bitti. "
            f"Average Queue: {average_queue:.2f}, "
            f"Max Queue: {max_queue}, "
            f"Min Queue: {min_queue}"
        )

    print(f"\nDetay CSV kaydedildi: {DETAIL_CSV_FILE}")
    print(f"Ozet CSV kaydedildi: {SUMMARY_CSV_FILE}")


# Komut satiri parametrelerini okur.
def parse_args():
    parser = argparse.ArgumentParser(
        description="Yeni normal sure agi icin default kuyruk olcumu"
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

    measure_default_queues(
        num_episodes=args.episodes,
        total_steps=args.steps,
        measure_interval=args.interval,
    )
