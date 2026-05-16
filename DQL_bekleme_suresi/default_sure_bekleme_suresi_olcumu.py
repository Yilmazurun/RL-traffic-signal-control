# ============================================
# IMPORTS
# ============================================

import argparse
import csv
import os
import sys

from kavsak_configleri import get_config, get_config_names

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
# GENERAL SETTINGS
# ============================================

USE_GUI = False
SUMO_BINARY = "sumo-gui" if USE_GUI else "sumo"

NUM_EPISODES = 1
TOTAL_STEPS = 12000
MEASURE_INTERVAL = 10

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


# ============================================
# CONFIG HELPERS
# ============================================


def get_output_paths(config):
    output_dir = config["output_dir"]

    return {
        "detail": os.path.join(output_dir, "default_sure_bekleme_suresi_detay.csv"),
        "summary": os.path.join(output_dir, "default_sure_bekleme_suresi_ozet.csv"),
    }


def get_phase_names(config):
    phase_names = {}

    for action in config["actions"]:
        phase_names[action["green_phase"]] = action["name"]

        if action.get("yellow_phase") is not None:
            phase_names[action["yellow_phase"]] = action["name"].replace("GREEN", "YELLOW")

    return phase_names


# ============================================
# SUMO HELPER FUNCTIONS
# ============================================


# Trafik isiginin mevcut phase indexini dondurur.
def get_current_phase(config):
    return traci.trafficlight.getPhase(config["tls_id"])


# Config'teki tum detector id'lerini tek listede toplar.
def get_all_detector_ids(config):
    detector_ids = []

    for group in config["detector_groups"]:
        detector_ids.extend(group["detectors"])

    return detector_ids


# Bu kavsagin detector alanlari icindeki arac id'lerini dondurur.
def get_local_vehicle_ids(config):
    vehicle_ids = set()

    for detector_id in get_all_detector_ids(config):
        for vehicle_id in traci.lanearea.getLastStepVehicleIDs(detector_id):
            vehicle_ids.add(vehicle_id)

    return vehicle_ids


# Secilen kavsagin detector alanlarindaki araclarin bekleme surelerini okur.
def get_waiting_time_snapshot(config):
    vehicle_ids = get_local_vehicle_ids(config)
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
def start_sumo_for_episode(config, episode_number):
    sumo_config = [
        SUMO_BINARY,
        "-c",
        config["sumo_config_file"],
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


def create_csv(file_path, fieldnames):
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def append_csv(file_path, fieldnames, row):
    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(row)


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
def measure_default_waiting_times(config, num_episodes, total_steps, measure_interval):
    os.makedirs(config["output_dir"], exist_ok=True)

    paths = get_output_paths(config)
    phase_names = get_phase_names(config)

    create_csv(paths["detail"], DETAIL_FIELDS)
    create_csv(paths["summary"], SUMMARY_FIELDS)

    print("\n=== DEFAULT SURE BEKLEME SURESI OLCUMU BASLADI ===")
    print("Trafik isigina mudahale edilmiyor; agdaki sureler aynen kullaniliyor.")
    print(f"Config: {config['name']} ({config['title']})")
    print(f"TLS: {config['tls_id']}")
    print(f"Output dir: {config['output_dir']}")

    for episode in range(1, num_episodes + 1):
        print(f"\n========== EPISODE {episode}/{num_episodes} ==========")

        start_sumo_for_episode(config, episode - 1)

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
                ) = get_waiting_time_snapshot(config)

                phase = get_current_phase(config)

                detail_rows.append(
                    {
                        "episode": episode,
                        "time": current_time,
                        "phase": phase,
                        "phase_name": phase_names.get(phase, "UNKNOWN"),
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
                        f"Phase: {phase_names.get(phase, 'UNKNOWN')}, "
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

        append_csv_rows(paths["detail"], DETAIL_FIELDS, detail_rows)

        append_csv(
            paths["summary"],
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

    print(f"\nDetay CSV kaydedildi: {paths['detail']}")
    print(f"Ozet CSV kaydedildi: {paths['summary']}")


# ============================================
# CLI
# ============================================


def parse_args():
    parser = argparse.ArgumentParser(
        description="Config tabanli default bekleme suresi olcumu"
    )
    parser.add_argument("--config", default="turkis_kavsak", choices=get_config_names())
    parser.add_argument("--episodes", type=int, default=NUM_EPISODES)
    parser.add_argument("--steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--interval", type=int, default=MEASURE_INTERVAL)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--list-configs", action="store_true")
    return parser.parse_args()


def main():
    global USE_GUI
    global SUMO_BINARY

    args = parse_args()

    if args.list_configs:
        print("\n".join(get_config_names()))
        return

    if args.gui:
        USE_GUI = True
        SUMO_BINARY = "sumo-gui"

    config = get_config(args.config)

    measure_default_waiting_times(
        config=config,
        num_episodes=args.episodes,
        total_steps=args.steps,
        measure_interval=args.interval,
    )


if __name__ == "__main__":
    main()
