import argparse
import csv
import os
import random
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import namedtuple
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULT_DIR = SCRIPT_DIR / "sonuclar"

BASE_SUMO_CONFIG = PROJECT_ROOT / "yeni_normal_sure.sumocfg"
BASE_NET_FILE = PROJECT_ROOT / "yeni_normal_sure.net.xml"
BASE_ROUTE_FILE = PROJECT_ROOT / "arac_talepleri" / "deneme_1.rou.xml"
BASE_DETECTOR_FILE = PROJECT_ROOT / "Detectors" / "detector_deneme.add.xml"

TEST_ROUTE_FILE = SCRIPT_DIR / "test_araclari.rou.xml"
CORRIDOR_DETECTOR_FILE = SCRIPT_DIR / "detector_koridor.add.xml"
DETECTOR_OUTPUT_DIR = SCRIPT_DIR / "detector_ciktilari"
DEFAULT_SUMO_CONFIG = SCRIPT_DIR / "default_koridor.sumocfg"
DQL_SUMO_CONFIG = SCRIPT_DIR / "dql_koridor.sumocfg"
GREEN_WAVE_NET_FILE = SCRIPT_DIR / "green_wave_koridor.net.xml"
GREEN_WAVE_SUMO_CONFIG = SCRIPT_DIR / "green_wave_koridor.sumocfg"
GREEN_WAVE_OFFSETS_FILE = SCRIPT_DIR / "green_wave_offsetleri.csv"

START_EDGE = "-4841"
END_EDGE = "-4779.656.62.62"
TEST_VEHICLE_PREFIX = "test_be_"
TEST_VEHICLE_COUNT = 100
DEPART_BEGIN = 0.0
DEPART_END = 12000.0
RANDOM_SEED = 42

GREEN_WAVE_SPEED_KMH = 80.0
GREEN_WAVE_CYCLE = 120.0
GREEN_WAVE_REFERENCE_DISTANCE = 1166.61

TOTAL_STEPS = 24000
DECISION_INTERVAL = 10
MIN_GREEN_STEPS = 20
YELLOW_STEPS = 3
QUEUE_NORMALIZER = 40.0

TRAVEL_TIME_FIELDS = [
    "mode",
    "vehicle_id",
    "depart_time",
    "arrival_time",
    "travel_time",
]

SUMMARY_FIELDS = [
    "mode",
    "test_vehicle_count",
    "completed_vehicle_count",
    "missing_vehicle_count",
    "average_travel_time",
    "median_travel_time",
    "min_travel_time",
    "max_travel_time",
    "first_depart_time",
    "last_arrival_time",
    "output_file",
]

DQL_CONFIG_NAMES = [
    "atakum_lisesi_kavsak",
    "yesilyurt_avm_kavsak",
    "mimar_sinan_kavsak",
    "turkis_kavsak",
    "omurevleri_kavsak",
    "atakent_kavsak",
    "yenimahalle_gobek",
    "pelitkoy_kavsak",
    "korfez_kavsak",
    "turgut_ozal_kavsak",
]

GREEN_WAVE_POINTS = [
    ("atakum_lisesi_kavsak", 1166.61),
    ("yesilyurt_avm_kavsak", 2052.51),
    ("mimar_sinan_kavsak", 2454.75),
    ("turkis_kavsak", 3208.90),
    ("omurevleri_kavsak", 4189.25),
    ("atakent_kavsak", 5676.82),
    ("yenimahalle_kavsak", 6797.88),
    ("pelitkoy_kavsak", 7767.89),
    ("korfez_kavsak", 8374.28),
    ("turgut_ozal_kavsak", 9902.74),
]


if "SUMO_HOME" in os.environ:
    SUMO_TOOLS = Path(os.environ["SUMO_HOME"]) / "tools"
    sys.path.append(str(SUMO_TOOLS))
else:
    sys.exit("SUMO_HOME environment variable is not defined")

import sumolib
import traci


def ensure_dql_path():
    dql_dir = PROJECT_ROOT / "DQL_bekleme_suresi"
    if str(dql_dir) not in sys.path:
        sys.path.insert(0, str(dql_dir))


def get_corridor_edges():
    net = sumolib.net.readNet(str(BASE_NET_FILE))
    start_edge = net.getEdge(START_EDGE)
    end_edge = net.getEdge(END_EDGE)
    path, cost = net.getOptimalPath(start_edge, end_edge)

    if not path:
        raise RuntimeError(f"Koridor rotasi bulunamadi: {START_EDGE} -> {END_EDGE}")

    return [edge.getID() for edge in path], cost


def write_test_routes():
    route_edges, cost = get_corridor_edges()
    rng = random.Random(RANDOM_SEED)
    departs = sorted(rng.uniform(DEPART_BEGIN, DEPART_END) for _ in range(TEST_VEHICLE_COUNT))

    root = ET.Element(
        "routes",
        {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:noNamespaceSchemaLocation": "http://sumo.dlr.de/xsd/routes_file.xsd",
        },
    )
    ET.SubElement(root, "vType", {"id": "test_passenger", "vClass": "passenger"})
    ET.SubElement(root, "route", {"id": "test_be_route", "edges": " ".join(route_edges)})

    for index, depart in enumerate(departs):
        ET.SubElement(
            root,
            "vehicle",
            {
                "id": f"{TEST_VEHICLE_PREFIX}{index:03d}",
                "type": "test_passenger",
                "route": "test_be_route",
                "depart": f"{depart:.2f}",
                "departLane": "best",
                "departSpeed": "max",
            },
        )

    ET.indent(root, space="    ")
    tree = ET.ElementTree(root)
    tree.write(TEST_ROUTE_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Test route yazildi: {TEST_ROUTE_FILE}")
    print(f"Koridor edge sayisi: {len(route_edges)}, yaklasik uzunluk: {cost:.2f} m")


def write_sumo_config(file_path, net_file):
    route_files = ",".join(
        [
            "../arac_talepleri/deneme_1.rou.xml",
            "test_araclari.rou.xml",
        ]
    )

    config = f"""<?xml version="1.0" encoding="UTF-8"?>
<sumoConfiguration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{net_file}"/>
        <route-files value="{route_files}"/>
        <additional-files value="detector_koridor.add.xml"/>
    </input>
</sumoConfiguration>
"""

    file_path.write_text(config, encoding="utf-8")
    print(f"SUMO config yazildi: {file_path}")


def write_corridor_detectors():
    DETECTOR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(BASE_DETECTOR_FILE)
    root = tree.getroot()

    for element in root.iter():
        detector_id = element.get("id")
        if detector_id and element.get("file") is not None:
            element.set("file", f"detector_ciktilari/{detector_id}.xml")

    ET.indent(tree, space="    ")
    tree.write(CORRIDOR_DETECTOR_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Koridor detector additional yazildi: {CORRIDOR_DETECTOR_FILE}")


def green_wave_offsets():
    speed_mps = GREEN_WAVE_SPEED_KMH / 3.6
    offsets = {}

    for tls_id, distance in GREEN_WAVE_POINTS:
        travel_delta = (distance - GREEN_WAVE_REFERENCE_DISTANCE) / speed_mps
        arrival_mod = travel_delta % GREEN_WAVE_CYCLE
        offset = (GREEN_WAVE_CYCLE - arrival_mod) % GREEN_WAVE_CYCLE
        offsets[tls_id] = round(offset, 2)

    return offsets


def scaled_phase_durations(phases):
    green_indices = [index for index in range(len(phases)) if index % 2 == 0]
    fixed_indices = [index for index in range(len(phases)) if index not in green_indices]

    original_green_total = sum(float(phases[index].get("duration")) for index in green_indices)
    fixed_total = sum(float(phases[index].get("duration")) for index in fixed_indices)
    new_green_total = GREEN_WAVE_CYCLE - fixed_total

    if original_green_total <= 0 or new_green_total <= 0:
        raise RuntimeError("Green-wave phase sureleri olceklenemedi.")

    durations = [float(phase.get("duration")) for phase in phases]
    scaled_total = 0.0

    for index in green_indices[:-1]:
        duration = float(phases[index].get("duration")) / original_green_total * new_green_total
        durations[index] = round(duration, 2)
        scaled_total += durations[index]

    last_green = green_indices[-1]
    durations[last_green] = round(new_green_total - scaled_total, 2)

    return durations


def write_green_wave_net():
    offsets = green_wave_offsets()
    tree = ET.parse(BASE_NET_FILE)
    root = tree.getroot()

    for tl_logic in root.findall("tlLogic"):
        tls_id = tl_logic.get("id")
        if tls_id not in offsets:
            continue

        phases = tl_logic.findall("phase")
        durations = scaled_phase_durations(phases)

        tl_logic.set("offset", f"{offsets[tls_id]:.2f}")

        for phase, duration in zip(phases, durations):
            phase.set("duration", f"{duration:.2f}")

    ET.indent(tree, space="    ")
    tree.write(GREEN_WAVE_NET_FILE, encoding="utf-8", xml_declaration=True)
    write_green_wave_offset_csv(offsets)
    print(f"Green-wave net yazildi: {GREEN_WAVE_NET_FILE}")


def write_green_wave_offset_csv(offsets):
    speed_mps = GREEN_WAVE_SPEED_KMH / 3.6

    with GREEN_WAVE_OFFSETS_FILE.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "tls_id",
            "distance_m",
            "speed_kmh",
            "cycle_s",
            "arrival_mod_s",
            "offset_s",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for tls_id, distance in GREEN_WAVE_POINTS:
            travel_delta = (distance - GREEN_WAVE_REFERENCE_DISTANCE) / speed_mps
            arrival_mod = travel_delta % GREEN_WAVE_CYCLE
            writer.writerow(
                {
                    "tls_id": tls_id,
                    "distance_m": f"{distance:.2f}",
                    "speed_kmh": f"{GREEN_WAVE_SPEED_KMH:.2f}",
                    "cycle_s": f"{GREEN_WAVE_CYCLE:.2f}",
                    "arrival_mod_s": f"{arrival_mod:.2f}",
                    "offset_s": f"{offsets[tls_id]:.2f}",
                }
            )

    print(f"Green-wave offset CSV yazildi: {GREEN_WAVE_OFFSETS_FILE}")


def prepare_files():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    write_test_routes()
    write_corridor_detectors()
    write_green_wave_net()
    write_sumo_config(DEFAULT_SUMO_CONFIG, "../yeni_normal_sure.net.xml")
    write_sumo_config(DQL_SUMO_CONFIG, "../yeni_normal_sure.net.xml")
    write_sumo_config(GREEN_WAVE_SUMO_CONFIG, "green_wave_koridor.net.xml")


def load_test_vehicle_ids():
    tree = ET.parse(TEST_ROUTE_FILE)
    root = tree.getroot()
    return {
        vehicle.get("id")
        for vehicle in root.findall("vehicle")
        if vehicle.get("id", "").startswith(TEST_VEHICLE_PREFIX)
    }


def get_output_path(mode):
    return RESULT_DIR / f"{mode}_travel_times.csv"


def create_travel_time_csv(file_path):
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAVEL_TIME_FIELDS)
        writer.writeheader()


def write_travel_time_rows(file_path, rows):
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAVEL_TIME_FIELDS)
        writer.writerows(rows)


def update_summary(mode, rows, test_vehicle_count, output_file):
    completed = len(rows)
    travel_times = [float(row["travel_time"]) for row in rows]
    depart_times = [float(row["depart_time"]) for row in rows]
    arrival_times = [float(row["arrival_time"]) for row in rows]

    summary_row = {
        "mode": mode,
        "test_vehicle_count": test_vehicle_count,
        "completed_vehicle_count": completed,
        "missing_vehicle_count": test_vehicle_count - completed,
        "average_travel_time": f"{statistics.mean(travel_times):.2f}" if travel_times else "",
        "median_travel_time": f"{statistics.median(travel_times):.2f}" if travel_times else "",
        "min_travel_time": f"{min(travel_times):.2f}" if travel_times else "",
        "max_travel_time": f"{max(travel_times):.2f}" if travel_times else "",
        "first_depart_time": f"{min(depart_times):.2f}" if depart_times else "",
        "last_arrival_time": f"{max(arrival_times):.2f}" if arrival_times else "",
        "output_file": str(output_file),
    }

    summary_file = RESULT_DIR / "karsilastirma_ozet.csv"
    existing = []

    if summary_file.exists():
        with summary_file.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing = [row for row in reader if row.get("mode") != mode]

    existing.append(summary_row)

    mode_order = {"default": 0, "green_wave": 1, "dql": 2}
    existing.sort(key=lambda row: mode_order.get(row["mode"], 99))

    with summary_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(existing)

    print(f"Ozet guncellendi: {summary_file}")


def start_sumo(sumo_config_file, gui, seed):
    binary = "sumo-gui" if gui else "sumo"
    command = [
        binary,
        "-c",
        str(sumo_config_file),
        "--step-length",
        "1",
        "--lateral-resolution",
        "0",
        "--seed",
        str(seed),
        "--no-step-log",
        "true",
        "--duration-log.disable",
        "true",
    ]

    if gui:
        command += ["--delay", "50"]

    traci.start(command)


class DQNController:
    def __init__(self, config, model, device):
        self.config = config
        self.model = model
        self.device = device
        self.action_to_green = {
            index: action["green_phase"]
            for index, action in enumerate(config["actions"])
        }
        self.green_to_yellow = {
            action["green_phase"]: action["yellow_phase"]
            for action in config["actions"]
            if action.get("yellow_phase") is not None
        }
        self.pending_green = None
        self.yellow_until = None
        self.last_switch_time = 0.0

    def initialize(self):
        first_green = self.config["actions"][0]["green_phase"]
        traci.trafficlight.setPhase(self.config["tls_id"], first_green)
        traci.trafficlight.setPhaseDuration(self.config["tls_id"], 9999)
        self.last_switch_time = traci.simulation.getTime()

    def step(self):
        current_time = traci.simulation.getTime()

        if self.pending_green is not None:
            if current_time >= self.yellow_until:
                traci.trafficlight.setPhase(self.config["tls_id"], self.pending_green)
                traci.trafficlight.setPhaseDuration(self.config["tls_id"], 9999)
                self.pending_green = None
                self.yellow_until = None
                self.last_switch_time = current_time
            return

        if current_time - self.last_switch_time < MIN_GREEN_STEPS:
            return

        if int(current_time) % DECISION_INTERVAL != 0:
            return

        action = self.choose_action()
        target_green = self.action_to_green[action]
        current_phase = traci.trafficlight.getPhase(self.config["tls_id"])

        if current_phase == target_green:
            return

        if current_phase in self.green_to_yellow:
            yellow_phase = self.green_to_yellow[current_phase]
            traci.trafficlight.setPhase(self.config["tls_id"], yellow_phase)
            traci.trafficlight.setPhaseDuration(self.config["tls_id"], YELLOW_STEPS)
            self.pending_green = target_green
            self.yellow_until = current_time + YELLOW_STEPS
        else:
            traci.trafficlight.setPhase(self.config["tls_id"], target_green)
            traci.trafficlight.setPhaseDuration(self.config["tls_id"], 9999)
            self.last_switch_time = current_time

    def choose_action(self):
        state = get_dql_state(self.config)

        import torch

        with torch.no_grad():
            tensor = torch.tensor(state, dtype=torch.float32, device=self.device)
            q_values = self.model(tensor.unsqueeze(0))
            return int(torch.argmax(q_values, dim=1).item())


def get_queue_sum(detectors):
    total = 0

    for detector_id in detectors:
        total += traci.lanearea.getLastStepVehicleNumber(detector_id)

    return total


def phase_to_action_group(config, phase):
    for index, action in enumerate(config["actions"]):
        if phase == action["green_phase"] or phase == action.get("yellow_phase"):
            return index

    return 0


def get_dql_state(config):
    detector_values = []

    for group in config["detector_groups"]:
        detector_values.append(get_queue_sum(group["detectors"]) / QUEUE_NORMALIZER)

    action_size = len(config["actions"])
    current_group = phase_to_action_group(config, traci.trafficlight.getPhase(config["tls_id"]))
    phase_one_hot = np.zeros(action_size, dtype=np.float32)
    phase_one_hot[current_group] = 1.0

    state = np.array(detector_values + phase_one_hot.tolist(), dtype=np.float32)
    return np.clip(state, 0.0, 5.0)


def load_dql_controllers(allow_missing_models):
    ensure_dql_path()

    import torch
    import torch.nn as nn
    from kavsak_configleri import get_config

    class DQN(nn.Module):
        def __init__(self, state_size, action_size):
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(state_size, 128),
                nn.ReLU(),
                nn.Linear(128, 128),
                nn.ReLU(),
                nn.Linear(128, action_size),
            )

        def forward(self, x):
            return self.network(x)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    controllers = []
    main_module = sys.modules.get("__main__")

    if main_module is not None and not hasattr(main_module, "Transition"):
        main_module.Transition = namedtuple(
            "Transition",
            ("state", "action", "reward", "next_state", "done"),
        )

    for config_name in DQL_CONFIG_NAMES:
        config = get_config(config_name)
        model_path = Path(config["output_dir"]) / "dql_bekleme_suresi_model.pth"

        if not model_path.exists():
            message = f"DQL modeli bulunamadi: {model_path}"
            if allow_missing_models:
                print(f"Uyari: {message}. Bu kavsak atlandi.")
                continue
            raise RuntimeError(message)

        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        state_size = len(config["detector_groups"]) + len(config["actions"])
        action_size = len(config["actions"])

        if checkpoint.get("state_size") not in [None, state_size]:
            raise RuntimeError(f"State size uyumsuz: {config_name}")

        if checkpoint.get("action_size") not in [None, action_size]:
            raise RuntimeError(f"Action size uyumsuz: {config_name}")

        model = DQN(state_size, action_size).to(device)
        model.load_state_dict(checkpoint["policy_net"])
        model.eval()
        controllers.append(DQNController(config, model, device))

    print(f"DQL controller sayisi: {len(controllers)}")
    return controllers


def validate_dql_detectors(controllers):
    available = set(traci.lanearea.getIDList())
    missing = []

    for controller in controllers:
        for group in controller.config["detector_groups"]:
            for detector_id in group["detectors"]:
                if detector_id not in available:
                    missing.append((controller.config["name"], detector_id))

    if missing:
        details = ", ".join(f"{name}:{detector_id}" for name, detector_id in missing)
        raise RuntimeError(f"Eksik detector var: {details}")


def measure_mode(mode, sumo_config_file, max_steps, gui, seed, allow_missing_models):
    test_vehicle_ids = load_test_vehicle_ids()
    output_file = get_output_path(mode)
    create_travel_time_csv(output_file)

    controllers = []
    if mode == "dql":
        controllers = load_dql_controllers(allow_missing_models)

    print(f"\n=== {mode} koridor seyahat suresi olcumu basladi ===")
    print(f"SUMO config: {sumo_config_file}")
    print(f"Test araci: {len(test_vehicle_ids)}")

    start_sumo(sumo_config_file, gui=gui, seed=seed)

    if controllers:
        validate_dql_detectors(controllers)
        for controller in controllers:
            controller.initialize()

    depart_times = {}
    rows = []

    try:
        while traci.simulation.getTime() < max_steps and len(rows) < len(test_vehicle_ids):
            if controllers:
                for controller in controllers:
                    controller.step()

            traci.simulationStep()
            current_time = float(traci.simulation.getTime())

            for vehicle_id in traci.simulation.getDepartedIDList():
                if vehicle_id in test_vehicle_ids:
                    depart_times[vehicle_id] = current_time

            for vehicle_id in traci.simulation.getArrivedIDList():
                if vehicle_id not in test_vehicle_ids:
                    continue

                depart_time = depart_times.get(vehicle_id)
                if depart_time is None:
                    continue

                rows.append(
                    {
                        "mode": mode,
                        "vehicle_id": vehicle_id,
                        "depart_time": f"{depart_time:.2f}",
                        "arrival_time": f"{current_time:.2f}",
                        "travel_time": f"{current_time - depart_time:.2f}",
                    }
                )

            if int(current_time) % 1000 == 0:
                print(
                    f"Time: {int(current_time)}, "
                    f"departed test: {len(depart_times)}, "
                    f"arrived test: {len(rows)}"
                )

    finally:
        traci.close()

    rows.sort(key=lambda row: row["vehicle_id"])
    write_travel_time_rows(output_file, rows)
    update_summary(mode, rows, len(test_vehicle_ids), output_file)

    print(f"{mode} detay CSV kaydedildi: {output_file}")
    print(f"Tamamlanan test araci: {len(rows)}/{len(test_vehicle_ids)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Koridor seyahat suresi olcumu")
    parser.add_argument(
        "--mode",
        choices=["default", "green_wave", "dql", "all"],
        default="all",
    )
    parser.add_argument("--max-steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--allow-missing-models", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    prepare_files()

    if args.prepare_only:
        return

    modes = ["default", "green_wave", "dql"] if args.mode == "all" else [args.mode]
    configs = {
        "default": DEFAULT_SUMO_CONFIG,
        "green_wave": GREEN_WAVE_SUMO_CONFIG,
        "dql": DQL_SUMO_CONFIG,
    }

    for mode in modes:
        measure_mode(
            mode=mode,
            sumo_config_file=configs[mode],
            max_steps=args.max_steps,
            gui=args.gui,
            seed=args.seed,
            allow_missing_models=args.allow_missing_models,
        )


if __name__ == "__main__":
    main()
