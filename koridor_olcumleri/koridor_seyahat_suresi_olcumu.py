import argparse
import csv
import os
import random
import re
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, namedtuple
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
RESULT_DIR = SCRIPT_DIR / "sonuclar"
RUN_SUMMARY_DIR = RESULT_DIR / "ozetler"

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
GREEN_WAVE_FIXED_NET_FILE = SCRIPT_DIR / "green_wave_fixed_koridor.net.xml"
GREEN_WAVE_FIXED_SUMO_CONFIG = SCRIPT_DIR / "green_wave_fixed_koridor.sumocfg"
GREEN_WAVE_FIXED_OFFSETS_FILE = SCRIPT_DIR / "green_wave_fixed_offsetleri.csv"
OFFSET_CHECK_FILE = RESULT_DIR / "ofset_dogrulama.csv"
SUMMARY_FILE = RESULT_DIR / "karsilastirma_ozet.csv"
MULTI_SEED_FILE = RESULT_DIR / "karsilastirma_coklu_tohum.csv"

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
CORRIDOR_VIEW_MARGIN = 250.0

# dql_safe guvenlik katmani varsayilanlari.
SAFE_YELLOW_STEPS = 5
MAX_RED_STEPS = 90

OLD_MODES = ["default", "green_wave", "dql"]
NEW_MODES = ["green_wave_fixed", "dql_safe"]
ALL_MODES = OLD_MODES + NEW_MODES
DQL_MODES = ["dql", "dql_safe"]

TRAVEL_TIME_FIELDS = [
    "mode",
    "vehicle_id",
    "depart_time",
    "arrival_time",
    "travel_time",
    "seed",
    "planned_depart_time",
    "insertion_delay",
    "total_time",
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
    "seed",
    "max_steps",
    "end_time",
    "average_total_time",
    "median_total_time",
    "average_insertion_delay",
    "never_departed_count",
    "departed_not_arrived_count",
    "teleport_count",
    "emergency_stop_count",
    "emergency_braking_count",
    "collision_count",
    "red_light_emergency_stop_count",
    "yellowless_red_switch_count",
    "override_count",
    "top_teleport_flows",
    "wall_clock_s",
]

MULTI_SEED_METRICS = [
    "average_travel_time",
    "average_total_time",
    "average_insertion_delay",
    "completed_vehicle_count",
    "teleport_count",
    "emergency_stop_count",
    "red_light_emergency_stop_count",
    "yellowless_red_switch_count",
    "override_count",
]

MISSING_FIELDS = [
    "mode",
    "seed",
    "vehicle_id",
    "status",
    "planned_depart_time",
    "depart_time",
    "edge",
    "lane",
    "lane_tls",
    "next_tls",
    "next_tls_distance",
    "next_tls_state",
    "waiting_time",
    "accumulated_waiting_time",
    "speed",
    "end_time",
]

NOT_DEPARTED_STATUSES = ["girmedi", "planlanan_zaman_gelmedi"]

OFFSET_CHECK_FIELDS = [
    "mode",
    "tls_id",
    "offset_s",
    "observed_phase0_start_mod_s",
    "difference_s",
    "ok",
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

CORRIDOR_TLS_IDS = [tls_id for tls_id, _ in GREEN_WAVE_POINTS]

TELEPORT_PATTERN = re.compile(r"Teleporting vehicle '([^']+)'")
RED_LIGHT_STOP_PATTERN = re.compile(
    r"Vehicle '([^']+)' performs emergency stop at the end of lane '([^']+)' because of a red traffic light"
)
EMERGENCY_BRAKING_PATTERN = re.compile(r"Vehicle '([^']+)' performs emergency braking")
COLLISION_PATTERN = re.compile(r"collision with vehicle", re.IGNORECASE)


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


def relative_to_script(path):
    try:
        return Path(path).resolve().relative_to(SCRIPT_DIR).as_posix()
    except ValueError:
        return str(path)


# Dosya icerigi degismediyse yeniden yazmaz. Paralel kosularda SUMO bir
# dosyayi okurken baska bir surecin ayni dosyayi bastan yazmasini onler.
def write_bytes_if_changed(file_path, data):
    file_path = Path(file_path)
    if file_path.exists() and file_path.read_bytes() == data:
        return False

    tmp_path = file_path.with_name(file_path.name + f".{os.getpid()}.tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, file_path)
    return True


def write_tree_if_changed(tree, file_path):
    ET.indent(tree, space="    ")
    data = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
    return write_bytes_if_changed(file_path, data)


def get_corridor_edges():
    net = sumolib.net.readNet(str(BASE_NET_FILE))
    start_edge = net.getEdge(START_EDGE)
    end_edge = net.getEdge(END_EDGE)
    path, cost = net.getOptimalPath(start_edge, end_edge)

    if not path:
        raise RuntimeError(f"Koridor rotasi bulunamadi: {START_EDGE} -> {END_EDGE}")

    return [edge.getID() for edge in path], cost


def get_corridor_boundary():
    net = sumolib.net.readNet(str(BASE_NET_FILE))
    route_edges, _ = get_corridor_edges()
    xs = []
    ys = []

    for edge_id in route_edges:
        edge = net.getEdge(edge_id)
        shape = edge.getShape(includeJunctions=True) or edge.getRawShape()

        for x, y in shape:
            xs.append(x)
            ys.append(y)

    if not xs or not ys:
        raise RuntimeError("Koridor gorunum sinirlari hesaplanamadi.")

    return (
        min(xs) - CORRIDOR_VIEW_MARGIN,
        min(ys) - CORRIDOR_VIEW_MARGIN,
        max(xs) + CORRIDOR_VIEW_MARGIN,
        max(ys) + CORRIDOR_VIEW_MARGIN,
    )


def focus_gui_on_corridor():
    view_id = "View #0"

    try:
        traci.gui.setSchema(view_id, "real world")
    except Exception:
        pass

    try:
        xmin, ymin, xmax, ymax = get_corridor_boundary()
        traci.gui.setBoundary(view_id, xmin, ymin, xmax, ymax)
        print("SUMO-GUI koridor bolgesine odaklandi.")
    except Exception as exc:
        print(f"GUI koridor gorunumu ayarlanamadi: {exc}")


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
    ET.SubElement(
        root,
        "vType",
        {
            "id": "test_passenger",
            "vClass": "passenger",
            "color": "255,0,255",
        },
    )
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

    if write_tree_if_changed(ET.ElementTree(root), TEST_ROUTE_FILE):
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

    if write_bytes_if_changed(file_path, config.encode("utf-8")):
        print(f"SUMO config yazildi: {file_path}")


def build_detector_tree(output_prefix):
    tree = ET.parse(BASE_DETECTOR_FILE)
    root = tree.getroot()

    for element in root.iter():
        detector_id = element.get("id")
        if detector_id and element.get("file") is not None:
            element.set("file", f"{output_prefix}{detector_id}.xml")

    return tree


def write_corridor_detectors():
    DETECTOR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tree = build_detector_tree("detector_ciktilari/")

    if write_tree_if_changed(tree, CORRIDOR_DETECTOR_FILE):
        print(f"Koridor detector additional yazildi: {CORRIDOR_DETECTOR_FILE}")


# Her kosu icin detector ciktilari ayri klasore gider; paralel kosular ayni
# dosyaya yazmaz. Additional dosyasi da o klasorun icine yazilir.
def write_run_detector_file(run_tag):
    run_dir = DETECTOR_OUTPUT_DIR / run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    add_file = run_dir / "detector_kosu.add.xml"
    write_tree_if_changed(build_detector_tree(""), add_file)
    return add_file


def green_wave_arrival_mods():
    speed_mps = GREEN_WAVE_SPEED_KMH / 3.6
    arrival_mods = {}

    for tls_id, distance in GREEN_WAVE_POINTS:
        travel_delta = (distance - GREEN_WAVE_REFERENCE_DISTANCE) / speed_mps
        arrival_mods[tls_id] = travel_delta % GREEN_WAVE_CYCLE

    return arrival_mods


# Rapordaki green_wave modunun ofsetleri. Isaret ters (bkz. green_wave_fixed);
# sonuclar karsilastirilabilsin diye degistirilmeden birakildi.
def green_wave_offsets():
    offsets = {}

    for tls_id, arrival_mod in green_wave_arrival_mods().items():
        offset = (GREEN_WAVE_CYCLE - arrival_mod) % GREEN_WAVE_CYCLE
        offsets[tls_id] = round(offset, 2)

    return offsets


# SUMO'da pozitif offset programi geciktirir: faz 0, t = offset (mod cevrim)
# aninda baslar. Arac kavsaga arrival_mod saniye sonra ulastigi icin dogru
# ofset arrival_mod'dur.
def green_wave_fixed_offsets():
    offsets = {}

    for tls_id, arrival_mod in green_wave_arrival_mods().items():
        offsets[tls_id] = round(arrival_mod % GREEN_WAVE_CYCLE, 2)

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


def write_green_wave_net(offsets=None, net_file=GREEN_WAVE_NET_FILE, offsets_file=GREEN_WAVE_OFFSETS_FILE):
    if offsets is None:
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

    changed = write_tree_if_changed(tree, net_file)
    write_green_wave_offset_csv(offsets, offsets_file)

    if changed:
        print(f"Green-wave net yazildi: {net_file}")


def write_green_wave_offset_csv(offsets, offsets_file=GREEN_WAVE_OFFSETS_FILE):
    fieldnames = [
        "tls_id",
        "distance_m",
        "speed_kmh",
        "cycle_s",
        "arrival_mod_s",
        "offset_s",
    ]
    arrival_mods = green_wave_arrival_mods()
    lines = [",".join(fieldnames)]

    for tls_id, distance in GREEN_WAVE_POINTS:
        lines.append(
            ",".join(
                [
                    tls_id,
                    f"{distance:.2f}",
                    f"{GREEN_WAVE_SPEED_KMH:.2f}",
                    f"{GREEN_WAVE_CYCLE:.2f}",
                    f"{arrival_mods[tls_id]:.2f}",
                    f"{offsets[tls_id]:.2f}",
                ]
            )
        )

    data = ("\r\n".join(lines) + "\r\n").encode("utf-8")

    if write_bytes_if_changed(offsets_file, data):
        print(f"Green-wave offset CSV yazildi: {offsets_file}")


def prepare_files():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    write_test_routes()
    write_corridor_detectors()
    write_green_wave_net()
    write_green_wave_net(
        offsets=green_wave_fixed_offsets(),
        net_file=GREEN_WAVE_FIXED_NET_FILE,
        offsets_file=GREEN_WAVE_FIXED_OFFSETS_FILE,
    )
    write_sumo_config(DEFAULT_SUMO_CONFIG, "../yeni_normal_sure.net.xml")
    write_sumo_config(DQL_SUMO_CONFIG, "../yeni_normal_sure.net.xml")
    write_sumo_config(GREEN_WAVE_SUMO_CONFIG, "green_wave_koridor.net.xml")
    write_sumo_config(GREEN_WAVE_FIXED_SUMO_CONFIG, "green_wave_fixed_koridor.net.xml")


def load_test_vehicles():
    tree = ET.parse(TEST_ROUTE_FILE)
    root = tree.getroot()
    return {
        vehicle.get("id"): float(vehicle.get("depart"))
        for vehicle in root.findall("vehicle")
        if vehicle.get("id", "").startswith(TEST_VEHICLE_PREFIX)
    }


def load_test_vehicle_ids():
    return set(load_test_vehicles())


def run_tag(mode, seed):
    return f"{mode}_s{seed}"


def get_output_path(mode, seed):
    return RESULT_DIR / f"{run_tag(mode, seed)}_travel_times.csv"


def get_diagnostic_paths(mode, seed):
    tag = run_tag(mode, seed)
    return {
        "tripinfo": RESULT_DIR / f"tripinfo_{tag}.xml",
        "stats": RESULT_DIR / f"stats_{tag}.xml",
        "log": RESULT_DIR / f"log_{tag}.txt",
        "missing": RESULT_DIR / f"eksik_araclar_{tag}.csv",
    }


def create_travel_time_csv(file_path):
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAVEL_TIME_FIELDS)
        writer.writeheader()


def write_travel_time_rows(file_path, rows):
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAVEL_TIME_FIELDS)
        writer.writerows(rows)


def format_value(value):
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def parse_statistics(stats_file):
    result = {}

    if not stats_file or not Path(stats_file).exists():
        return result

    try:
        root = ET.parse(stats_file).getroot()
    except ET.ParseError as exc:
        print(f"Uyari: statistic dosyasi okunamadi: {exc}")
        return result

    teleports = root.find("teleports")
    if teleports is not None:
        result["teleport_count"] = int(float(teleports.get("total", 0)))

    safety = root.find("safety")
    if safety is not None:
        result["emergency_stop_count"] = int(float(safety.get("emergencyStops", 0)))
        result["emergency_braking_count"] = int(float(safety.get("emergencyBraking", 0)))
        result["collision_count"] = int(float(safety.get("collisions", 0)))

    return result


def flow_id_of(vehicle_id):
    return vehicle_id.rsplit(".", 1)[0] if "." in vehicle_id else vehicle_id


def parse_log(log_file, lane_to_tls=None):
    result = {
        "red_light_emergency_stop_count": 0,
        "log_teleport_count": 0,
        "teleport_flows": Counter(),
        "red_light_stop_tls": Counter(),
    }

    if not log_file or not Path(log_file).exists():
        return result

    lane_to_tls = lane_to_tls or {}

    with Path(log_file).open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            match = TELEPORT_PATTERN.search(line)
            if match:
                result["log_teleport_count"] += 1
                result["teleport_flows"][flow_id_of(match.group(1))] += 1
                continue

            match = RED_LIGHT_STOP_PATTERN.search(line)
            if match:
                result["red_light_emergency_stop_count"] += 1
                lane_id = match.group(2)
                result["red_light_stop_tls"][lane_to_tls.get(lane_id, lane_id)] += 1

    return result


def parse_tripinfo_test_vehicles(tripinfo_file):
    result = {}

    if not tripinfo_file or not Path(tripinfo_file).exists():
        return result

    try:
        root = ET.parse(tripinfo_file).getroot()
    except ET.ParseError as exc:
        print(f"Uyari: tripinfo dosyasi okunamadi: {exc}")
        return result

    for trip in root.findall("tripinfo"):
        vehicle_id = trip.get("id", "")
        if vehicle_id.startswith(TEST_VEHICLE_PREFIX):
            result[vehicle_id] = {
                "depart": float(trip.get("depart", -1)),
                "arrival": float(trip.get("arrival", -1)),
                "waitingTime": float(trip.get("waitingTime", 0)),
            }

    return result


def build_summary_row(mode, seed, rows, test_vehicle_count, output_file, extra):
    completed = len(rows)
    travel_times = [float(row["travel_time"]) for row in rows]
    total_times = [float(row["total_time"]) for row in rows]
    insertion_delays = [float(row["insertion_delay"]) for row in rows]
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
        "output_file": relative_to_script(output_file),
        "seed": seed,
        "average_total_time": f"{statistics.mean(total_times):.2f}" if total_times else "",
        "median_total_time": f"{statistics.median(total_times):.2f}" if total_times else "",
        "average_insertion_delay": f"{statistics.mean(insertion_delays):.2f}" if insertion_delays else "",
    }

    for field in SUMMARY_FIELDS:
        if field not in summary_row:
            summary_row[field] = format_value(extra.get(field, ""))

    return summary_row


def write_run_summary(summary_row):
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    run_file = RUN_SUMMARY_DIR / f"ozet_{run_tag(summary_row['mode'], summary_row['seed'])}.csv"

    with run_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerow(summary_row)

    return run_file


def read_run_summaries():
    rows = []

    if not RUN_SUMMARY_DIR.exists():
        return rows

    for run_file in sorted(RUN_SUMMARY_DIR.glob("ozet_*.csv")):
        with run_file.open("r", newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))

    return rows


def mode_sort_key(row):
    mode_order = {mode: index for index, mode in enumerate(ALL_MODES)}
    try:
        seed = int(row.get("seed") or 0)
    except ValueError:
        seed = 0
    return mode_order.get(row["mode"], 99), seed


# Tum kosu ozetlerinden karsilastirma_ozet.csv ve
# karsilastirma_coklu_tohum.csv dosyalarini yeniden uretir.
def update_summary():
    rows = read_run_summaries()
    rows.sort(key=mode_sort_key)

    with SUMMARY_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Ozet guncellendi: {SUMMARY_FILE}")
    write_multi_seed_summary(rows)


def write_multi_seed_summary(rows):
    fieldnames = ["mode", "seed_count", "seeds"]
    for metric in MULTI_SEED_METRICS:
        fieldnames += [f"{metric}_mean", f"{metric}_std"]

    by_mode = {}
    for row in rows:
        by_mode.setdefault(row["mode"], []).append(row)

    output_rows = []
    for mode in sorted(by_mode, key=lambda name: mode_sort_key({"mode": name})):
        mode_rows = by_mode[mode]
        output = {
            "mode": mode,
            "seed_count": len(mode_rows),
            "seeds": " ".join(str(row["seed"]) for row in mode_rows),
        }

        for metric in MULTI_SEED_METRICS:
            values = [float(row[metric]) for row in mode_rows if row.get(metric) not in (None, "")]
            output[f"{metric}_mean"] = f"{statistics.mean(values):.2f}" if values else ""
            output[f"{metric}_std"] = f"{statistics.stdev(values):.2f}" if len(values) > 1 else ""

        output_rows.append(output)

    with MULTI_SEED_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Coklu tohum ozeti guncellendi: {MULTI_SEED_FILE}")


def start_sumo(sumo_config_file, gui, seed, diagnostics=None, additional_file=None):
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

    if additional_file is not None:
        command += ["--additional-files", str(additional_file)]

    if diagnostics:
        command += [
            "--tripinfo-output",
            str(diagnostics["tripinfo"]),
            "--tripinfo-output.write-unfinished",
            "true",
            "--statistic-output",
            str(diagnostics["stats"]),
            "--log",
            str(diagnostics["log"]),
        ]

    if gui:
        command += ["--delay", "50"]

    traci.start(command)

    if gui:
        focus_gui_on_corridor()


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
        self.override_count = 0

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


# Ayni egitilmis model; ustune guvenlik katmani eklenir:
# 1) Sari gecis, net dosyasindaki sari faz yerine mevcut ve hedef yesil
#    durumlarindan uretilir (G/g -> r olan her baglanti sari yanar).
# 2) Azami kirmizi: MAX_RED saniyedir yesil almayan bir baglantiyi kullanmak
#    icin duran arac varsa model karari yerine o baglantiyi hizmet eden
#    action secilir. Kontrol serit degil baglanti bazlidir; ayni seritte hep
#    yesil olan bir baglanti, digerinin acligini gizlemesin.
class SafeDQNController(DQNController):
    def __init__(self, config, model, device, max_red=MAX_RED_STEPS, yellow_steps=SAFE_YELLOW_STEPS):
        super().__init__(config, model, device)
        self.max_red = max_red
        self.yellow_steps = yellow_steps
        self.tls_id = config["tls_id"]
        self.program_id = None
        self.green_states = {}
        self.action_links = {}
        self.link_actions = {}
        self.link_lanes = {}
        self.contested_links = []
        self.last_green_time = {}
        self.current_action = 0
        self.pending_action = None
        self.transition_count = 0

    def build_link_maps(self):
        self.program_id = traci.trafficlight.getProgram(self.tls_id)
        logic = None

        for candidate in traci.trafficlight.getAllProgramLogics(self.tls_id):
            if candidate.programID == self.program_id:
                logic = candidate
                break

        if logic is None:
            raise RuntimeError(f"TLS programi bulunamadi: {self.tls_id}")

        controlled_links = traci.trafficlight.getControlledLinks(self.tls_id)

        for link_index, links in enumerate(controlled_links):
            if links:
                self.link_lanes[link_index] = links[0][0]

        for action_index, green_phase in self.action_to_green.items():
            state = logic.phases[green_phase].state
            self.green_states[action_index] = state
            self.action_links[action_index] = {
                link_index
                for link_index in self.link_lanes
                if link_index < len(state) and state[link_index] in "Gg"
            }

        for link_index in sorted(self.link_lanes):
            actions = [index for index, links in self.action_links.items() if link_index in links]
            self.link_actions[link_index] = actions

            # Her action'da yesil (veya hic yesil almayan) baglanti izlenmez.
            if 0 < len(actions) < len(self.action_links):
                self.contested_links.append(link_index)

    def initialize(self):
        self.build_link_maps()
        super().initialize()
        now = traci.simulation.getTime()
        self.current_action = 0
        self.last_green_time = {link_index: now for link_index in self.link_lanes}

    def mark_green(self, now):
        for link_index in self.action_links[self.current_action]:
            self.last_green_time[link_index] = now

    def transition_state(self, target_action):
        current_state = self.green_states[self.current_action]
        target_state = self.green_states[target_action]
        chars = []

        for current_char, target_char in zip(current_state, target_state):
            if current_char in "Gg" and target_char == "r":
                chars.append("y")
            else:
                chars.append(current_char)

        return "".join(chars)

    def switch_to_green(self, action, now):
        traci.trafficlight.setProgram(self.tls_id, self.program_id)
        traci.trafficlight.setPhase(self.tls_id, self.action_to_green[action])
        traci.trafficlight.setPhaseDuration(self.tls_id, 9999)
        self.current_action = action
        self.last_switch_time = now
        self.mark_green(now)

    # Seritte duran ve siradaki isik baglantisi bu baglanti olan arac var mi?
    def has_halting_vehicle_for_link(self, link_index):
        lane_id = self.link_lanes[link_index]

        if traci.lane.getLastStepHaltingNumber(lane_id) <= 0:
            return False

        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id):
            if traci.vehicle.getSpeed(vehicle_id) >= 0.1:
                continue

            next_tls = traci.vehicle.getNextTLS(vehicle_id)
            if next_tls and next_tls[0][0] == self.tls_id and next_tls[0][1] == link_index:
                return True

        return False

    def starved_action(self, model_action, now):
        starved = []

        for link_index in self.contested_links:
            if link_index in self.action_links[self.current_action]:
                continue

            red_time = now - self.last_green_time[link_index]
            if red_time < self.max_red:
                continue

            if not self.has_halting_vehicle_for_link(link_index):
                continue

            starved.append((red_time, link_index))

        if not starved:
            return None

        starved.sort(reverse=True)
        oldest_link = starved[0][1]
        candidates = self.link_actions[oldest_link]

        if model_action in candidates:
            return model_action

        starved_links = {link_index for _, link_index in starved}
        return max(
            candidates,
            key=lambda action: (len(self.action_links[action] & starved_links), -action),
        )

    def step(self):
        now = traci.simulation.getTime()

        if self.pending_action is not None:
            if now >= self.yellow_until:
                self.switch_to_green(self.pending_action, now)
                self.pending_action = None
                self.yellow_until = None
            return

        self.mark_green(now)

        if now - self.last_switch_time < MIN_GREEN_STEPS:
            return

        if int(now) % DECISION_INTERVAL != 0:
            return

        model_action = self.choose_action()
        action = model_action
        forced_action = self.starved_action(model_action, now)

        if forced_action is not None and forced_action != model_action:
            action = forced_action
            self.override_count += 1

        if action == self.current_action:
            return

        yellow_state = self.transition_state(action)

        if yellow_state == self.green_states[self.current_action]:
            self.switch_to_green(action, now)
            return

        traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)
        self.pending_action = action
        self.yellow_until = now + self.yellow_steps
        self.transition_count += 1


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


def load_dql_controllers(allow_missing_models, safe=False, max_red=MAX_RED_STEPS, yellow_steps=SAFE_YELLOW_STEPS):
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

        if safe:
            controllers.append(SafeDQNController(config, model, device, max_red=max_red, yellow_steps=yellow_steps))
        else:
            controllers.append(DQNController(config, model, device))

    print(f"DQL controller sayisi: {len(controllers)}" + (" (guvenlik katmani acik)" if safe else ""))
    return controllers


def build_controllers(mode, args):
    if mode not in DQL_MODES:
        return []

    return load_dql_controllers(
        args.allow_missing_models,
        safe=(mode == "dql_safe"),
        max_red=args.max_red,
        yellow_steps=args.safe_yellow,
    )


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


def build_lane_to_tls():
    lane_to_tls = {}

    for tls_id in traci.trafficlight.getIDList():
        for lane_id in traci.trafficlight.getControlledLanes(tls_id):
            lane_to_tls.setdefault(lane_id, tls_id)

    return lane_to_tls


# Sari yanmadan yesilden (G/g) kirmiziya (r) gecen baglantilari sayar.
class YellowlessSwitchMonitor:
    def __init__(self, tls_ids):
        available = set(traci.trafficlight.getIDList())
        self.tls_ids = [tls_id for tls_id in tls_ids if tls_id in available]
        self.previous = {tls_id: traci.trafficlight.getRedYellowGreenState(tls_id) for tls_id in self.tls_ids}
        self.count = 0
        self.by_tls = Counter()

    def step(self):
        for tls_id in self.tls_ids:
            state = traci.trafficlight.getRedYellowGreenState(tls_id)
            previous = self.previous[tls_id]

            if state != previous:
                switched = sum(
                    1
                    for old_char, new_char in zip(previous, state)
                    if old_char in "Gg" and new_char == "r"
                )
                if switched:
                    self.count += switched
                    self.by_tls[tls_id] += switched
                self.previous[tls_id] = state


def describe_missing_vehicles(mode, seed, planned_departs, depart_times, arrived_ids, lane_to_tls, end_time):
    rows = []
    active = set(traci.vehicle.getIDList())

    for vehicle_id in sorted(planned_departs):
        if vehicle_id in arrived_ids:
            continue

        row = {field: "" for field in MISSING_FIELDS}
        row.update(
            {
                "mode": mode,
                "seed": seed,
                "vehicle_id": vehicle_id,
                "planned_depart_time": f"{planned_departs[vehicle_id]:.2f}",
                "end_time": f"{end_time:.2f}",
            }
        )

        if vehicle_id not in depart_times and planned_departs[vehicle_id] > end_time:
            # Olcum, aracin planlanan kalkis zamanindan once bitti.
            row["status"] = "planlanan_zaman_gelmedi"
        elif vehicle_id not in depart_times:
            # Planlanan zaman gecti ama giris kuyrugundan aga giremedi.
            row["status"] = "girmedi"
        elif vehicle_id in active:
            lane_id = traci.vehicle.getLaneID(vehicle_id)
            row.update(
                {
                    "status": "takildi",
                    "depart_time": f"{depart_times[vehicle_id]:.2f}",
                    "edge": traci.vehicle.getRoadID(vehicle_id),
                    "lane": lane_id,
                    "lane_tls": lane_to_tls.get(lane_id, ""),
                    "waiting_time": f"{traci.vehicle.getWaitingTime(vehicle_id):.2f}",
                    "accumulated_waiting_time": f"{traci.vehicle.getAccumulatedWaitingTime(vehicle_id):.2f}",
                    "speed": f"{traci.vehicle.getSpeed(vehicle_id):.2f}",
                }
            )
            next_tls = traci.vehicle.getNextTLS(vehicle_id)
            if next_tls:
                tls_id, _, distance, state = next_tls[0]
                row.update(
                    {
                        "next_tls": tls_id,
                        "next_tls_distance": f"{distance:.2f}",
                        "next_tls_state": state,
                    }
                )
        else:
            row["status"] = "kalkti_ama_kayit_yok"
            row["depart_time"] = f"{depart_times[vehicle_id]:.2f}"

        rows.append(row)

    return rows


def write_missing_rows(file_path, rows):
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MISSING_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def measure_mode(mode, sumo_config_file, max_steps, gui, seed, args):
    planned_departs = load_test_vehicles()
    test_vehicle_ids = set(planned_departs)
    output_file = get_output_path(mode, seed)
    create_travel_time_csv(output_file)

    diagnostics = None if args.no_diagnostics else get_diagnostic_paths(mode, seed)
    additional_file = write_run_detector_file(run_tag(mode, seed))
    controllers = build_controllers(mode, args)

    print(f"\n=== {mode} koridor seyahat suresi olcumu basladi (seed {seed}) ===")
    print(f"SUMO config: {sumo_config_file}")
    print(f"Test araci: {len(test_vehicle_ids)}, max-steps: {max_steps}")

    wall_start = time.time()
    start_sumo(sumo_config_file, gui=gui, seed=seed, diagnostics=diagnostics, additional_file=additional_file)

    if controllers:
        validate_dql_detectors(controllers)
        for controller in controllers:
            controller.initialize()

    lane_to_tls = build_lane_to_tls()
    monitor = YellowlessSwitchMonitor(CORRIDOR_TLS_IDS)
    depart_times = {}
    rows = []
    arrived_ids = set()
    missing_rows = []
    current_time = float(traci.simulation.getTime())

    try:
        while traci.simulation.getTime() < max_steps and len(rows) < len(test_vehicle_ids):
            if controllers:
                for controller in controllers:
                    controller.step()

            traci.simulationStep()
            current_time = float(traci.simulation.getTime())
            monitor.step()

            for vehicle_id in traci.simulation.getDepartedIDList():
                if vehicle_id in test_vehicle_ids:
                    depart_times[vehicle_id] = current_time

            for vehicle_id in traci.simulation.getArrivedIDList():
                if vehicle_id not in test_vehicle_ids:
                    continue

                depart_time = depart_times.get(vehicle_id)
                if depart_time is None:
                    continue

                planned = planned_departs[vehicle_id]
                arrived_ids.add(vehicle_id)
                rows.append(
                    {
                        "mode": mode,
                        "vehicle_id": vehicle_id,
                        "depart_time": f"{depart_time:.2f}",
                        "arrival_time": f"{current_time:.2f}",
                        "travel_time": f"{current_time - depart_time:.2f}",
                        "seed": seed,
                        "planned_depart_time": f"{planned:.2f}",
                        "insertion_delay": f"{depart_time - planned:.2f}",
                        "total_time": f"{current_time - planned:.2f}",
                    }
                )

            if int(current_time) % 1000 == 0:
                print(
                    f"Time: {int(current_time)}, "
                    f"departed test: {len(depart_times)}, "
                    f"arrived test: {len(rows)}",
                    flush=True,
                )

            # Agda ve bekleyen kuyrukta arac kalmadiysa devam etmenin anlami yok.
            if traci.simulation.getMinExpectedNumber() == 0:
                print(f"Agda arac kalmadi, olcum {int(current_time)} s'de bitti.")
                break

        missing_rows = describe_missing_vehicles(
            mode, seed, planned_departs, depart_times, arrived_ids, lane_to_tls, current_time
        )

    finally:
        traci.close()

    wall_clock = time.time() - wall_start
    rows.sort(key=lambda row: row["vehicle_id"])
    write_travel_time_rows(output_file, rows)

    extra = {
        "max_steps": max_steps,
        "end_time": current_time,
        "never_departed_count": sum(1 for row in missing_rows if row["status"] in NOT_DEPARTED_STATUSES),
        "departed_not_arrived_count": sum(1 for row in missing_rows if row["status"] not in NOT_DEPARTED_STATUSES),
        "yellowless_red_switch_count": monitor.count,
        "override_count": sum(controller.override_count for controller in controllers) if mode == "dql_safe" else "",
        "wall_clock_s": round(wall_clock),
    }

    if diagnostics:
        write_missing_rows(diagnostics["missing"], missing_rows)
        extra.update(parse_statistics(diagnostics["stats"]))
        log_info = parse_log(diagnostics["log"], lane_to_tls)
        extra["red_light_emergency_stop_count"] = log_info["red_light_emergency_stop_count"]
        extra["top_teleport_flows"] = ";".join(
            f"{flow}:{count}" for flow, count in log_info["teleport_flows"].most_common(5)
        )
        check_tripinfo_consistency(diagnostics["tripinfo"], missing_rows)

        if log_info["red_light_stop_tls"]:
            details = ", ".join(f"{tls}:{count}" for tls, count in log_info["red_light_stop_tls"].most_common())
            print(f"Kirmizi isik acil duruslari (kavsak:sayi): {details}")

    if monitor.by_tls:
        details = ", ".join(f"{tls}:{count}" for tls, count in monitor.by_tls.most_common())
        print(f"Sarisiz G->r gecisleri (kavsak:baglanti): {details}")

    summary_row = build_summary_row(mode, seed, rows, len(test_vehicle_ids), output_file, extra)
    write_run_summary(summary_row)

    print(f"{mode} detay CSV kaydedildi: {output_file}")
    print(f"Tamamlanan test araci: {len(rows)}/{len(test_vehicle_ids)}")
    print(
        f"Ort. seyahat: {summary_row['average_travel_time']} s, "
        f"ort. toplam (giris gecikmesi dahil): {summary_row['average_total_time']} s, "
        f"isinlanma: {summary_row['teleport_count']}, acil durus: {summary_row['emergency_stop_count']}, "
        f"mudahale: {summary_row['override_count']}"
    )

    for row in missing_rows:
        if row["status"] == "planlanan_zaman_gelmedi":
            continue
        if row["status"] == "girmedi":
            print(f"  Eksik {row['vehicle_id']}: aga hic giremedi (planlanan {row['planned_depart_time']} s)")
        else:
            print(
                f"  Eksik {row['vehicle_id']}: takildi, serit {row['lane']}, "
                f"kavsak {row['lane_tls'] or row['next_tls']}, "
                f"bekleme {row['waiting_time']} s"
            )

    return summary_row


def check_tripinfo_consistency(tripinfo_file, missing_rows):
    trips = parse_tripinfo_test_vehicles(tripinfo_file)
    if not trips:
        return

    never_departed = {vehicle_id for vehicle_id, trip in trips.items() if trip["depart"] < 0}
    unfinished = {vehicle_id for vehicle_id, trip in trips.items() if trip["depart"] >= 0 and trip["arrival"] < 0}
    expected_never = {row["vehicle_id"] for row in missing_rows if row["status"] in NOT_DEPARTED_STATUSES}
    expected_unfinished = {row["vehicle_id"] for row in missing_rows if row["status"] not in NOT_DEPARTED_STATUSES}
    missing_in_tripinfo = expected_never - set(trips)

    print(
        f"Tripinfo: girmedi {len(never_departed)}, takildi {len(unfinished)} "
        f"(TraCI: girmedi {len(expected_never)}, takildi {len(expected_unfinished)})"
    )

    if missing_in_tripinfo:
        print(f"  Not: tripinfo'da hic yer almayan (yuklenmemis) arac: {len(missing_in_tripinfo)}")


def show_corridor(mode, sumo_config_file, max_steps, seed, args):
    controllers = build_controllers(mode, args)

    print(f"\n=== {mode} koridor GUI izleme modu ===")
    print("CSV olusturulmaz; sadece SUMO-GUI koridor bolgesine odaklanir.")
    print("Kapatmak icin SUMO-GUI penceresini kapatabilir veya terminalde Ctrl+C yapabilirsin.")

    start_sumo(sumo_config_file, gui=True, seed=seed)

    if controllers:
        validate_dql_detectors(controllers)
        for controller in controllers:
            controller.initialize()

    try:
        while traci.simulation.getTime() < max_steps:
            if controllers:
                for controller in controllers:
                    controller.step()

            traci.simulationStep()
            current_time = int(traci.simulation.getTime())

            if current_time % 1000 == 0:
                print(f"Time: {current_time}")
    except KeyboardInterrupt:
        print("GUI izleme modu kullanici tarafindan durduruldu.")
    except Exception as exc:
        print(f"GUI izleme modu kapandi: {exc}")
    finally:
        try:
            traci.close()
        except Exception:
            pass


# Her green-wave aginda faz 0'in gercekten offset saniyesinde basladigini
# kisa bir TraCI kosusuyla kontrol eder (sadece ag, trafik yok).
def verify_offsets():
    checks = [
        ("green_wave", GREEN_WAVE_NET_FILE, green_wave_offsets()),
        ("green_wave_fixed", GREEN_WAVE_FIXED_NET_FILE, green_wave_fixed_offsets()),
    ]
    rows = []
    all_ok = True

    for mode, net_file, offsets in checks:
        traci.start(
            [
                "sumo",
                "-n",
                str(net_file),
                "--step-length",
                "1",
                "--no-step-log",
                "true",
                "--duration-log.disable",
                "true",
                "--end",
                str(int(3 * GREEN_WAVE_CYCLE)),
            ]
        )
        first_start = {}

        try:
            phase0_duration = {}
            for tls_id in offsets:
                logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
                phase0_duration[tls_id] = logic.phases[0].duration

            previous_phase = {tls_id: traci.trafficlight.getPhase(tls_id) for tls_id in offsets}

            while traci.simulation.getTime() < 2 * GREEN_WAVE_CYCLE + 1:
                traci.simulationStep()

                for tls_id in offsets:
                    phase = traci.trafficlight.getPhase(tls_id)
                    if phase == 0 and previous_phase[tls_id] != 0 and tls_id not in first_start:
                        # Gercek baslangic ani = sonraki gecis - faz 0 suresi
                        first_start[tls_id] = traci.trafficlight.getNextSwitch(tls_id) - phase0_duration[tls_id]
                    previous_phase[tls_id] = phase
        finally:
            traci.close()

        for tls_id, offset in offsets.items():
            observed = first_start.get(tls_id)
            if observed is None:
                observed_mod = None
                difference = None
                ok = False
            else:
                observed_mod = observed % GREEN_WAVE_CYCLE
                difference = (observed_mod - offset + GREEN_WAVE_CYCLE / 2) % GREEN_WAVE_CYCLE - GREEN_WAVE_CYCLE / 2
                ok = abs(difference) < 0.01

            all_ok = all_ok and ok
            rows.append(
                {
                    "mode": mode,
                    "tls_id": tls_id,
                    "offset_s": f"{offset:.2f}",
                    "observed_phase0_start_mod_s": "" if observed_mod is None else f"{observed_mod:.2f}",
                    "difference_s": "" if difference is None else f"{difference:.2f}",
                    "ok": "evet" if ok else "hayir",
                }
            )

    with OFFSET_CHECK_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OFFSET_CHECK_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"{row['mode']:<17} {row['tls_id']:<22} offset {row['offset_s']:>7} "
            f"faz0 baslangic {row['observed_phase0_start_mod_s']:>7} -> {row['ok']}"
        )

    print(f"Ofset dogrulama {'basarili' if all_ok else 'BASARISIZ'}: {OFFSET_CHECK_FILE}")
    return all_ok


def child_command(mode, seed, args):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--mode",
        mode,
        "--seed",
        str(seed),
        "--max-steps",
        str(args.max_steps),
        "--max-red",
        str(args.max_red),
        "--safe-yellow",
        str(args.safe_yellow),
        "--skip-prepare",
        "--skip-aggregate",
    ]

    if args.no_diagnostics:
        command.append("--no-diagnostics")
    if args.allow_missing_models:
        command.append("--allow-missing-models")

    return command


# Mod x tohum kosularini ayri sureclerde paralel calistirir. Her surecin
# konsol ciktisi sonuclar/konsol_{mode}_s{seed}.txt dosyasina gider.
def run_parallel(runs, args):
    pending = list(runs)
    active = []
    failed = []

    print(f"{len(runs)} kosu, en fazla {args.jobs} paralel surec.")

    while pending or active:
        while pending and len(active) < args.jobs:
            mode, seed = pending.pop(0)
            console_file = RESULT_DIR / f"konsol_{run_tag(mode, seed)}.txt"
            handle = console_file.open("w", encoding="utf-8")
            process = subprocess.Popen(
                child_command(mode, seed, args),
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
            )
            active.append((mode, seed, process, handle, time.time()))
            print(f"Basladi: {mode} seed {seed} (konsol: {relative_to_script(console_file)})", flush=True)

        time.sleep(5)

        for item in list(active):
            mode, seed, process, handle, started = item
            if process.poll() is None:
                continue

            handle.close()
            active.remove(item)
            minutes = (time.time() - started) / 60.0

            if process.returncode == 0:
                print(f"Bitti: {mode} seed {seed} ({minutes:.1f} dk)", flush=True)
            else:
                failed.append((mode, seed))
                print(f"HATA: {mode} seed {seed} cikis kodu {process.returncode}", flush=True)

    return failed


def parse_args():
    parser = argparse.ArgumentParser(description="Koridor seyahat suresi olcumu")
    parser.add_argument(
        "--mode",
        nargs="+",
        choices=ALL_MODES + ["all", "hepsi"],
        default=["all"],
        help="all: eski uc mod (default, green_wave, dql); hepsi: yeni modlar dahil bes mod.",
    )
    parser.add_argument("--max-steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seeds", type=int, nargs="+", help="Birden fazla tohum; --seed yerine gecer.")
    parser.add_argument("--jobs", type=int, default=1, help="Paralel calisacak SUMO sureci sayisi.")
    parser.add_argument("--max-red", type=float, default=MAX_RED_STEPS, help="dql_safe azami kirmizi suresi (s).")
    parser.add_argument("--safe-yellow", type=int, default=SAFE_YELLOW_STEPS, help="dql_safe sari suresi (s).")
    parser.add_argument("--no-diagnostics", action="store_true", help="tripinfo/statistic/log ciktilarini kapatir.")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--show-corridor", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-offsets", action="store_true", help="Green-wave ofsetlerini TraCI ile dogrular.")
    parser.add_argument("--summarize-only", action="store_true", help="Sadece ozet CSV'lerini yeniden uretir.")
    parser.add_argument("--skip-prepare", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--skip-aggregate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-missing-models", action="store_true")
    return parser.parse_args()


def resolve_modes(requested):
    modes = []

    for mode in requested:
        if mode == "all":
            expanded = OLD_MODES
        elif mode == "hepsi":
            expanded = ALL_MODES
        else:
            expanded = [mode]

        for item in expanded:
            if item not in modes:
                modes.append(item)

    return modes


def main():
    args = parse_args()

    if not args.skip_prepare:
        prepare_files()

    if args.prepare_only:
        return

    if args.summarize_only:
        update_summary()
        return

    if args.verify_offsets:
        verify_offsets()
        return

    modes = resolve_modes(args.mode)
    seeds = args.seeds if args.seeds else [args.seed]
    configs = {
        "default": DEFAULT_SUMO_CONFIG,
        "green_wave": GREEN_WAVE_SUMO_CONFIG,
        "dql": DQL_SUMO_CONFIG,
        "green_wave_fixed": GREEN_WAVE_FIXED_SUMO_CONFIG,
        "dql_safe": DQL_SUMO_CONFIG,
    }

    if args.show_corridor:
        mode = "default" if args.mode == ["all"] else modes[0]
        show_corridor(
            mode=mode,
            sumo_config_file=configs[mode],
            max_steps=args.max_steps,
            seed=seeds[0],
            args=args,
        )
        return

    runs = [(mode, seed) for seed in seeds for mode in modes]

    if args.jobs > 1 and len(runs) > 1 and not args.gui:
        failed = run_parallel(runs, args)
        update_summary()
        if failed:
            sys.exit(f"Basarisiz kosular: {failed}")
        return

    for mode, seed in runs:
        measure_mode(
            mode=mode,
            sumo_config_file=configs[mode],
            max_steps=args.max_steps,
            gui=args.gui,
            seed=seed,
            args=args,
        )

    if not args.skip_aggregate:
        update_summary()


if __name__ == "__main__":
    main()
