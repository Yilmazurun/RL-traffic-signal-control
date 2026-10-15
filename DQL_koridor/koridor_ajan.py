"""Koridor farkindalikli, kalkanli, cok metrikli DQN ajani (ortak kod).

Egitim (train_koridor.py) ve olcum (koridor_olcumleri/koridor_seyahat_suresi_olcumu.py)
ayni durum, odul ve kalkan kodunu kullanir.

Yontem bilesenleri (her biri ayarlarla kapatilabilir, ablasyon icin):
- Durum: detector gruplarinda duran ve hareketli arac ayri (Advanced-XLight),
  her action icin "kac saniyedir yesil almadi" bilgisi, mevcut fazin suresi,
  koridordaki onceki ve sonraki kavsagin ana yol kuyrugu (CoLight'in sade hali).
- Odul: yerel bekleme + kavsak basinci (PressLight) + aclik cezasi
  (bekleyen araci olan en uzun kirmizi) + faz degistirme cezasi.
- Kalkan: azami kirmizi kurali egitim sirasinda da acik (shielded RL);
  ajan kuralin uygulandigi ortamda ogrenir. Dogru sari gecis her zaman aciktir.
"""
import os
import sys
from collections import namedtuple
from pathlib import Path

import numpy as np

if "SUMO_HOME" in os.environ:
    sys.path.append(str(Path(os.environ["SUMO_HOME"]) / "tools"))
else:
    sys.exit("SUMO_HOME environment variable is not defined")

import traci
import torch
import torch.nn as nn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DQL_DIR = PROJECT_ROOT / "DQL_bekleme_suresi"
RUNS_DIR = Path(__file__).resolve().parent / "egitimler"

# Koridor sirasiyla (Batipark -> Engiz). Komsuluk bu siradan cikarilir.
CONFIG_NAMES = [
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

MAIN_GROUP_NAMES = ("BATIPARK_ENGIZ", "ENGIZ_BATIPARK", "MAIN")

MIN_GREEN_STEPS = 20
DECISION_INTERVAL = 10
QUEUE_NORMALIZER = 40.0
RED_AGE_NORMALIZER = 120.0
PHASE_TIME_NORMALIZER = 60.0
STATE_CLIP = 5.0

DEFAULT_SETTINGS = {
    # Odul: "combo" (bekleme + basinc + aclik) veya "wait" (eski odul)
    "reward": "combo",
    "w_wait": 1.0,
    "w_pressure": 1.0,
    "w_starve": 1.0,
    "switch_penalty": 0.5,
    "reward_scale": 0.1,
    "reward_clip": 10.0,
    "starve_threshold": 60.0,
    # Durum bilesenleri
    "moving": True,
    "red_age": True,
    "neighbors": True,
    # Kalkan (azami kirmizi) ve sari
    "shield": True,
    "max_red": 90.0,
    "yellow": 5,
}

Transition = namedtuple("Transition", ("state", "action", "reward", "next_state", "done"))


def ensure_dql_path():
    if str(DQL_DIR) not in sys.path:
        sys.path.insert(0, str(DQL_DIR))


def load_configs():
    ensure_dql_path()
    from kavsak_configleri import get_config

    return [get_config(name) for name in CONFIG_NAMES]


class QNetwork(nn.Module):
    # Eski modelle ayni mimari; fark sadece durum, odul ve egitim ortaminda olsun.
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


class KoridorAgent:
    """Tek bir kavsagin isigini yoneten ajan: durum, odul, kalkan ve faz gecisi."""

    def __init__(self, config, settings, policy=None, device=None):
        self.config = config
        self.settings = settings
        self.tls_id = config["tls_id"]
        self.groups = config["detector_groups"]
        self.main_groups = [g for g in self.groups if g["name"] in MAIN_GROUP_NAMES] or self.groups[:1]
        self.action_to_green = {index: action["green_phase"] for index, action in enumerate(config["actions"])}
        self.action_size = len(self.action_to_green)
        self.upstream = None
        self.downstream = None
        self.policy = policy
        self.device = device
        self.override_count = 0
        self.decision_count = 0

    # ---------- kurulum ----------

    @property
    def state_size(self):
        size = len(self.groups) * (2 if self.settings["moving"] else 1)
        if self.settings["red_age"]:
            size += self.action_size
        size += self.action_size + 1
        if self.settings["neighbors"]:
            size += 2
        return size

    def build_link_maps(self):
        self.program_id = traci.trafficlight.getProgram(self.tls_id)
        logic = next(
            candidate
            for candidate in traci.trafficlight.getAllProgramLogics(self.tls_id)
            if candidate.programID == self.program_id
        )
        controlled_links = traci.trafficlight.getControlledLinks(self.tls_id)

        self.link_lanes = {}
        self.link_out_lanes = {}
        for link_index, links in enumerate(controlled_links):
            if links:
                self.link_lanes[link_index] = links[0][0]
                self.link_out_lanes[link_index] = links[0][1]

        self.green_states = {}
        self.action_links = {}
        for action, phase in self.action_to_green.items():
            state = logic.phases[phase].state
            self.green_states[action] = state
            self.action_links[action] = {
                link for link in self.link_lanes if link < len(state) and state[link] in "Gg"
            }

        self.link_actions = {}
        self.contested_links = []
        for link in sorted(self.link_lanes):
            actions = [action for action, links in self.action_links.items() if link in links]
            self.link_actions[link] = actions
            if 0 < len(actions) < self.action_size:
                self.contested_links.append(link)

        self.detector_ids = [d for group in self.groups for d in group["detectors"]]

    def initialize(self):
        self.build_link_maps()
        now = traci.simulation.getTime()
        traci.trafficlight.setPhase(self.tls_id, self.action_to_green[0])
        traci.trafficlight.setPhaseDuration(self.tls_id, 9999)
        self.current_action = 0
        self.pending_action = None
        self.yellow_until = None
        self.last_switch_time = now
        self.last_link_green = {link: now for link in self.link_lanes}
        self.last_action_active = {action: now for action in self.action_to_green}

    # ---------- faz gecisi ----------

    def update(self, now):
        """Her adim basinda cagrilir. Sari bittiyse hedef yesile gecer."""
        if self.pending_action is not None:
            if now >= self.yellow_until:
                self.switch_to_green(self.pending_action, now)
                self.pending_action = None
                self.yellow_until = None
            else:
                return

        for link in self.action_links[self.current_action]:
            self.last_link_green[link] = now
        self.last_action_active[self.current_action] = now

    def at_decision_point(self, now):
        return (
            self.pending_action is None
            and now - self.last_switch_time >= MIN_GREEN_STEPS
            and int(now) % DECISION_INTERVAL == 0
        )

    def switch_to_green(self, action, now):
        traci.trafficlight.setProgram(self.tls_id, self.program_id)
        traci.trafficlight.setPhase(self.tls_id, self.action_to_green[action])
        traci.trafficlight.setPhaseDuration(self.tls_id, 9999)
        self.current_action = action
        self.last_switch_time = now

    def apply(self, action, now):
        """Secilen action'a gecer. Faz degistiyse True doner."""
        if action == self.current_action:
            return False

        current_state = self.green_states[self.current_action]
        target_state = self.green_states[action]
        yellow_state = "".join(
            "y" if c in "Gg" and t == "r" else c for c, t in zip(current_state, target_state)
        )

        if yellow_state == current_state:
            self.switch_to_green(action, now)
        else:
            traci.trafficlight.setRedYellowGreenState(self.tls_id, yellow_state)
            self.pending_action = action
            self.yellow_until = now + self.settings["yellow"]

        return True

    # ---------- kalkan ----------

    def has_halting_vehicle_for_link(self, link):
        lane_id = self.link_lanes[link]
        if traci.lane.getLastStepHaltingNumber(lane_id) <= 0:
            return False

        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id):
            if traci.vehicle.getSpeed(vehicle_id) >= 0.1:
                continue
            next_tls = traci.vehicle.getNextTLS(vehicle_id)
            if next_tls and next_tls[0][0] == self.tls_id and next_tls[0][1] == link:
                return True

        return False

    def starved_links(self, now, min_age):
        starved = []
        for link in self.contested_links:
            if link in self.action_links[self.current_action]:
                continue
            age = now - self.last_link_green[link]
            if age >= min_age and self.has_halting_vehicle_for_link(link):
                starved.append((age, link))
        return sorted(starved, reverse=True)

    def shield(self, proposed, now):
        """Azami kirmizi kurali. Gerekirse onerilen action'i degistirir."""
        if not self.settings["shield"]:
            return proposed

        starved = self.starved_links(now, self.settings["max_red"])
        if not starved:
            return proposed

        candidates = self.link_actions[starved[0][1]]
        if proposed in candidates:
            return proposed

        starved_set = {link for _, link in starved}
        forced = max(candidates, key=lambda a: (len(self.action_links[a] & starved_set), -a))
        self.override_count += 1
        return forced

    # ---------- durum ----------

    def group_counts(self, group):
        halting = 0
        total = 0
        for detector_id in group["detectors"]:
            halting += traci.lanearea.getLastStepHaltingNumber(detector_id)
            total += traci.lanearea.getLastStepVehicleNumber(detector_id)
        return halting, total

    def main_queue(self):
        return sum(self.group_counts(group)[0] for group in self.main_groups) / QUEUE_NORMALIZER

    def get_state(self, now):
        values = []
        for group in self.groups:
            halting, total = self.group_counts(group)
            if self.settings["moving"]:
                values += [halting / QUEUE_NORMALIZER, (total - halting) / QUEUE_NORMALIZER]
            else:
                values.append(total / QUEUE_NORMALIZER)

        if self.settings["red_age"]:
            values += [
                (now - self.last_action_active[action]) / RED_AGE_NORMALIZER
                for action in range(self.action_size)
            ]

        one_hot = [0.0] * self.action_size
        one_hot[self.current_action] = 1.0
        values += one_hot
        values.append((now - self.last_switch_time) / PHASE_TIME_NORMALIZER)

        if self.settings["neighbors"]:
            values.append(self.upstream.main_queue() if self.upstream else 0.0)
            values.append(self.downstream.main_queue() if self.downstream else 0.0)

        return np.clip(np.array(values, dtype=np.float32), 0.0, STATE_CLIP)

    # ---------- odul ----------

    def local_waiting_time(self):
        vehicles = set()
        for detector_id in self.detector_ids:
            vehicles.update(traci.lanearea.getLastStepVehicleIDs(detector_id))
        return sum(traci.vehicle.getWaitingTime(v) for v in vehicles)

    def pressure(self):
        total = 0
        for link, lane in self.link_lanes.items():
            total += traci.lane.getLastStepVehicleNumber(lane)
            total -= traci.lane.getLastStepVehicleNumber(self.link_out_lanes[link])
        return total

    def reward(self, now, switched):
        s = self.settings
        parts = {"wait": self.local_waiting_time() / 1000.0, "pressure": 0.0, "starve": 0.0}

        if s["reward"] == "combo":
            parts["pressure"] = abs(self.pressure()) / 100.0
            starved = self.starved_links(now, s["starve_threshold"])
            if starved:
                parts["starve"] = (starved[0][0] - s["starve_threshold"]) / 30.0

        cost = (
            s["w_wait"] * parts["wait"]
            + s["w_pressure"] * parts["pressure"]
            + s["w_starve"] * parts["starve"]
            + s["switch_penalty"] * (1.0 if switched else 0.0)
        )
        reward = max(-s["reward_clip"], -s["reward_scale"] * cost)
        return reward, parts

    # ---------- karar ----------

    def greedy_action(self, state):
        with torch.no_grad():
            tensor = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            return int(torch.argmax(self.policy(tensor), dim=1).item())

    def step(self):
        """Olcum (egitim disi) icin: kendi kendine karar veren, aciksiz ajan."""
        now = traci.simulation.getTime()
        self.update(now)
        if not self.at_decision_point(now):
            return
        state = self.get_state(now)
        action = self.shield(self.greedy_action(state), now)
        self.decision_count += 1
        self.apply(action, now)


def link_neighbors(agents):
    for index, agent in enumerate(agents):
        agent.upstream = agents[index - 1] if index > 0 else None
        agent.downstream = agents[index + 1] if index + 1 < len(agents) else None


def load_trained_agents(run_name, device=None):
    """Bir egitim kosusunun son modellerini olcum icin yukler."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_dir = RUNS_DIR / run_name
    checkpoint_file = run_dir / "modeller.pt"
    if not checkpoint_file.exists():
        raise RuntimeError(f"Egitilmis model bulunamadi: {checkpoint_file}")

    data = torch.load(checkpoint_file, map_location=device, weights_only=False)
    settings = {**DEFAULT_SETTINGS, **data["settings"]}
    agents = []

    for config in load_configs():
        agent = KoridorAgent(config, settings, device=device)
        policy = QNetwork(agent.state_size, agent.action_size).to(device)
        policy.load_state_dict(data["policies"][config["name"]])
        policy.eval()
        agent.policy = policy
        agents.append(agent)

    link_neighbors(agents)
    print(f"Koridor DQN yuklendi: {run_name} (bolum {data['episode']}), ayarlar: {settings}")
    return agents
