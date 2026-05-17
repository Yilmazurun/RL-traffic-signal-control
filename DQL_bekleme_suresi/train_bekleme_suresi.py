# ============================================
# IMPORTS
# ============================================

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
import csv
import random
import sys
import xml.etree.ElementTree as ET
from collections import deque, namedtuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

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

NUM_EPISODES = 10
TOTAL_STEPS = 12000
DECISION_INTERVAL = 10
MIN_GREEN_STEPS = 20
YELLOW_STEPS = 3

# ============================================
# DQL PARAMETERS
# ============================================

GAMMA = 0.95
LEARNING_RATE = 0.001
BATCH_SIZE = 64
MEMORY_SIZE = 50000
MIN_REPLAY_SIZE = 1000
TARGET_UPDATE_EVERY = 5

EPSILON_START = 1.0
EPSILON_MIN = 0.05
EPSILON_DECAY = 0.995

QUEUE_NORMALIZER = 40.0
WAITING_TIME_NORMALIZER = 1000.0
SWITCH_PENALTY = 0.5

CSV_FIELDS = [
    "episode",
    "run_episode",
    "total_steps",
    "reward",
    "average_waiting_time",
    "epsilon",
    "average_loss",
    "memory_size",
]

Transition = namedtuple(
    "Transition",
    ("state", "action", "reward", "next_state", "done"),
)

last_switch_time = 0


# ============================================
# CONFIG HELPERS
# ============================================


def get_output_paths(config):
    output_dir = config["output_dir"]

    return {
        "model": os.path.join(output_dir, "dql_bekleme_suresi_model.pth"),
        "stats": os.path.join(output_dir, "dql_bekleme_suresi_stats.csv"),
        "plots": [
            os.path.join(output_dir, "dql_bekleme_suresi_episode_reward.png"),
            os.path.join(output_dir, "dql_bekleme_suresi_average_waiting_time.png"),
            os.path.join(output_dir, "dql_bekleme_suresi_epsilon.png"),
        ],
    }


def get_state_size(config):
    return len(config["detector_groups"]) + len(config["actions"])


def get_action_size(config):
    return len(config["actions"])


def get_action_names(config):
    return {index: action["name"] for index, action in enumerate(config["actions"])}


def get_action_to_green_phase(config):
    return {
        index: action["green_phase"]
        for index, action in enumerate(config["actions"])
    }


def get_green_to_yellow_phase(config):
    return {
        action["green_phase"]: action["yellow_phase"]
        for action in config["actions"]
        if action.get("yellow_phase") is not None
    }


def validate_config_against_net(config):
    config_tree = ET.parse(config["sumo_config_file"])
    config_root = config_tree.getroot()
    net_file_element = config_root.find("./input/net-file")

    if net_file_element is None:
        raise RuntimeError(f"SUMO config icinde net-file bulunamadi: {config['sumo_config_file']}")

    net_file = net_file_element.get("value")
    net_file_path = os.path.join(os.path.dirname(config["sumo_config_file"]), net_file)

    tree = ET.parse(net_file_path)
    root = tree.getroot()
    tl_logic = None

    for candidate in root.findall("tlLogic"):
        if candidate.get("id") == config["tls_id"]:
            tl_logic = candidate
            break

    if tl_logic is None:
        raise RuntimeError(f"TLS bulunamadi: {config['tls_id']}")

    phases = tl_logic.findall("phase")
    max_phase_index = len(phases) - 1

    for action in config["actions"]:
        green_phase = action["green_phase"]
        yellow_phase = action.get("yellow_phase")

        if green_phase > max_phase_index:
            raise RuntimeError(
                f"{config['tls_id']} icin green_phase={green_phase} yok. "
                f"Kayitli net dosyasinda sadece {len(phases)} phase var."
            )

        if yellow_phase is not None and yellow_phase > max_phase_index:
            raise RuntimeError(
                f"{config['tls_id']} icin yellow_phase={yellow_phase} yok. "
                f"Kayitli net dosyasinda sadece {len(phases)} phase var. "
                "NetEdit'te faz degisikliklerini Save ettiginden emin ol."
            )

    return phases


# ============================================
# SUMO HELPERS
# ============================================


# Mevcut trafik isiginin aktif phase indexini dondurur.
def get_current_phase(config):
    return traci.trafficlight.getPhase(config["tls_id"])


# Trafik isigini verilen phase'e gecirir ve istenirse phase suresini ayarlar.
def set_phase(config, phase, duration=None):
    traci.trafficlight.setPhase(config["tls_id"], phase)

    if duration is not None:
        traci.trafficlight.setPhaseDuration(config["tls_id"], duration)


# Verilen lane area detector icindeki arac sayisini dondurur.
def get_queue_length(detector_id):
    return traci.lanearea.getLastStepVehicleNumber(detector_id)


# Verilen detector listesindeki toplam arac sayisini hesaplar.
def get_queue_sum(detectors):
    total = 0

    for detector_id in detectors:
        total += get_queue_length(detector_id)

    return total


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


# Aktif phase'in hangi action grubuna ait oldugunu dondurur.
def phase_to_action_group(config, phase):
    for index, action in enumerate(config["actions"]):
        if phase == action["green_phase"] or phase == action.get("yellow_phase"):
            return index

    return 0


# DQL ajaninin gorecegi sayisal state vektorunu uretir.
def get_state(config):
    detector_values = []

    for group in config["detector_groups"]:
        detector_values.append(
            get_queue_sum(group["detectors"]) / QUEUE_NORMALIZER
        )

    current_group = phase_to_action_group(config, get_current_phase(config))
    phase_one_hot = np.zeros(get_action_size(config), dtype=np.float32)
    phase_one_hot[current_group] = 1.0

    state = np.array(detector_values + phase_one_hot.tolist(), dtype=np.float32)

    return np.clip(state, 0.0, 5.0)


# Bu kavsagin detector alanlarindaki araclarin toplam bekleme suresini hesaplar.
def get_local_waiting_time(config):
    total_waiting_time = 0.0

    for vehicle_id in get_local_vehicle_ids(config):
        total_waiting_time += traci.vehicle.getWaitingTime(vehicle_id)

    return total_waiting_time


# Toplam bekleme suresine gore negatif reward uretir.
def get_reward(total_waiting_time, action, previous_action):
    reward = -float(total_waiting_time) / WAITING_TIME_NORMALIZER

    if action != previous_action:
        reward -= SWITCH_PENALTY

    return reward


# Secilen action'i trafik isigina uygular.
def apply_action(config, action):
    global last_switch_time

    current_phase = get_current_phase(config)
    action_to_green_phase = get_action_to_green_phase(config)
    green_to_yellow_phase = get_green_to_yellow_phase(config)
    target_green_phase = action_to_green_phase[action]

    if current_phase == target_green_phase:
        return

    if current_phase in green_to_yellow_phase:
        yellow_phase = green_to_yellow_phase[current_phase]
        set_phase(config, yellow_phase, YELLOW_STEPS)

        for _ in range(YELLOW_STEPS):
            traci.simulationStep()

    set_phase(config, target_green_phase, 9999)
    last_switch_time = traci.simulation.getTime()


# Minimum yesil suresi doldu mu kontrol eder.
def can_switch():
    current_time = traci.simulation.getTime()
    return current_time - last_switch_time >= MIN_GREEN_STEPS


# Her episode icin SUMO'yu bastan baslatir.
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
# DQL MODEL
# ============================================


class DQN(nn.Module):
    # State vektorunden her action icin Q degeri tahmin eden kucuk sinir agi.
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


class ReplayMemory:
    # Ajanin gecmis deneyimlerini saklar; egitimde rastgele mini-batch secilir.
    def __init__(self, capacity):
        self.memory = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.memory.append(Transition(state, action, reward, next_state, done))

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


class DQLAgent:
    # Epsilon-greedy action secimi, replay memory ve model optimizasyonunu yonetir.
    def __init__(self, device, state_size, action_size):
        self.device = device
        self.state_size = state_size
        self.action_size = action_size
        self.policy_net = DQN(state_size, action_size).to(device)
        self.target_net = DQN(state_size, action_size).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=LEARNING_RATE)
        self.loss_fn = nn.SmoothL1Loss()
        self.memory = ReplayMemory(MEMORY_SIZE)
        self.epsilon = EPSILON_START
        self.completed_episodes = 0

    # Kayitli model varsa egitime oradan devam eder.
    def load_if_exists(self, model_file):
        if not os.path.exists(model_file):
            print("Yeni DQL modeli olusturuldu.")
            return

        checkpoint = torch.load(model_file, map_location=self.device, weights_only=False)

        if checkpoint.get("state_size") not in [None, self.state_size]:
            raise RuntimeError("Model state size bu kavsak config'i ile uyumlu degil.")

        if checkpoint.get("action_size") not in [None, self.action_size]:
            raise RuntimeError("Model action size bu kavsak config'i ile uyumlu degil.")

        self.policy_net.load_state_dict(checkpoint["policy_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.epsilon = checkpoint.get("epsilon", EPSILON_START)
        self.completed_episodes = int(checkpoint.get("episode", 0))

        if "memory" in checkpoint:
            self.memory.memory = deque(checkpoint["memory"], maxlen=MEMORY_SIZE)

        print(
            f"DQL modeli yuklendi: {model_file} "
            f"(tamamlanan toplam episode: {self.completed_episodes})"
        )

    # Policy, target network, optimizer, replay memory ve epsilon degerini diske kaydeder.
    def save(self, model_file, episode, config_name):
        torch.save(
            {
                "config_name": config_name,
                "episode": episode,
                "state_size": self.state_size,
                "action_size": self.action_size,
                "policy_net": self.policy_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "memory": list(self.memory.memory),
            },
            model_file,
        )

    # Epsilon-greedy yontemle bazen rastgele, bazen modelin en iyi gordugu action'i secer.
    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.randrange(self.action_size)

        with torch.no_grad():
            state_tensor = torch.tensor(state, dtype=torch.float32, device=self.device)
            q_values = self.policy_net(state_tensor.unsqueeze(0))
            return int(torch.argmax(q_values, dim=1).item())

    # Replay memory'den batch alip DQL Bellman hedefi ile policy network'u gunceller.
    def optimize_model(self):
        if len(self.memory) < max(MIN_REPLAY_SIZE, BATCH_SIZE):
            return None

        transitions = self.memory.sample(BATCH_SIZE)
        batch = Transition(*zip(*transitions))

        state_batch = torch.tensor(np.array(batch.state), dtype=torch.float32, device=self.device)
        action_batch = torch.tensor(batch.action, dtype=torch.int64, device=self.device).unsqueeze(1)
        reward_batch = torch.tensor(batch.reward, dtype=torch.float32, device=self.device)
        next_state_batch = torch.tensor(np.array(batch.next_state), dtype=torch.float32, device=self.device)
        done_batch = torch.tensor(batch.done, dtype=torch.float32, device=self.device)

        current_q = self.policy_net(state_batch).gather(1, action_batch).squeeze(1)

        with torch.no_grad():
            next_q = self.target_net(next_state_batch).max(1)[0]
            target_q = reward_batch + GAMMA * next_q * (1.0 - done_batch)

        loss = self.loss_fn(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()

        return float(loss.item())

    # Target network'u policy network ile esitler; egitimi daha stabil yapar.
    def update_target_network(self):
        self.target_net.load_state_dict(self.policy_net.state_dict())

    # Kesfi zamanla azaltir.
    def decay_epsilon(self):
        self.epsilon = max(EPSILON_MIN, self.epsilon * EPSILON_DECAY)


# ============================================
# TRAINING UTILITIES
# ============================================


def append_stats(stats_file, row):
    file_exists = os.path.exists(stats_file)
    file_is_empty = (not file_exists) or os.path.getsize(stats_file) == 0

    with open(stats_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)

        if file_is_empty:
            writer.writeheader()

        writer.writerow(row)


def read_stats_history(stats_file):
    if not os.path.exists(stats_file):
        return []

    history = []

    with open(stats_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                history.append(
                    {
                        "episode": int(row["episode"]),
                        "reward": float(row["reward"]),
                        "average_waiting_time": float(row.get("average_waiting_time", 0.0)),
                        "epsilon": float(row["epsilon"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

    return history


def save_plots(history, plot_files):
    if not history:
        return

    episodes = [row["episode"] for row in history]

    plt.figure(figsize=(10, 5))
    plt.plot(episodes, [row["reward"] for row in history])
    plt.xlabel("Episode")
    plt.ylabel("Cumulative Reward")
    plt.title("DQL Episode Reward")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(plot_files[0])
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(episodes, [row["average_waiting_time"] for row in history])
    plt.xlabel("Episode")
    plt.ylabel("Average Waiting Time")
    plt.title("DQL Average Waiting Time per Episode")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(plot_files[1])
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(episodes, [row["epsilon"] for row in history])
    plt.xlabel("Episode")
    plt.ylabel("Epsilon")
    plt.title("DQL Epsilon Decay")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(plot_files[2])
    plt.close()


def clean_outputs(paths):
    for file_path in [paths["model"], paths["stats"]] + paths["plots"]:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Eski cikti silindi: {file_path}")


# ============================================
# TRAINING LOOP
# ============================================


def train(config, num_episodes, total_steps, resume):
    global last_switch_time

    os.makedirs(config["output_dir"], exist_ok=True)

    paths = get_output_paths(config)
    state_size = get_state_size(config)
    action_size = get_action_size(config)
    action_names = get_action_names(config)
    phases = validate_config_against_net(config)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Config: {config['name']} ({config['title']})")
    print(f"TLS: {config['tls_id']}")
    print(f"Layout: {config['layout']}")
    print(f"Net phase count: {len(phases)}")
    print(f"State size: {state_size}, Action size: {action_size}")
    print(f"Output dir: {config['output_dir']}")

    agent = DQLAgent(device, state_size, action_size)

    if resume:
        agent.load_if_exists(paths["model"])
    else:
        print("Resume kapali; model sifirdan egitilecek.")

    start_episode = agent.completed_episodes
    end_episode = start_episode + num_episodes
    first_green_phase = config["actions"][0]["green_phase"]

    print("\n=== DQL EPISODE TRAINING STARTED ===")
    print(f"Bu kosuda {num_episodes} episode egitilecek.")
    print(f"Toplam episode araligi: {start_episode + 1}-{end_episode}")

    for run_episode in range(1, num_episodes + 1):
        episode = start_episode + run_episode
        print(
            f"\n========== TOTAL EPISODE {episode}/{end_episode} "
            f"(RUN {run_episode}/{num_episodes}) =========="
        )

        start_sumo_for_episode(config, episode - 1)

        last_switch_time = 0
        set_phase(config, first_green_phase, 9999)
        last_switch_time = traci.simulation.getTime()

        cumulative_reward = 0.0
        decision_count = 0
        waiting_time_sum_for_episode = 0.0
        waiting_time_record_count = 0
        losses = []

        previous_action = 0

        try:
            while traci.simulation.getTime() < total_steps:
                old_state = get_state(config)

                if can_switch():
                    action = agent.choose_action(old_state)
                else:
                    action = phase_to_action_group(config, get_current_phase(config))

                apply_action(config, action)

                for _ in range(DECISION_INTERVAL):
                    if traci.simulation.getTime() >= total_steps:
                        break
                    traci.simulationStep()

                done = traci.simulation.getTime() >= total_steps
                new_state = get_state(config)
                total_waiting_time = get_local_waiting_time(config)
                reward = get_reward(total_waiting_time, action, previous_action)

                agent.memory.push(old_state, action, reward, new_state, done)
                loss = agent.optimize_model()

                if loss is not None:
                    losses.append(loss)

                cumulative_reward += reward
                decision_count += 1
                previous_action = action
                agent.decay_epsilon()

                waiting_time_sum_for_episode += total_waiting_time
                waiting_time_record_count += 1

                if decision_count % 50 == 0:
                    current_time = int(traci.simulation.getTime())
                    average_loss = sum(losses[-50:]) / max(len(losses[-50:]), 1)

                    print(
                        f"Episode: {episode}, "
                        f"Run Episode: {run_episode}, "
                        f"Time: {current_time}, "
                        f"Action: {action_names[action]}, "
                        f"Reward: {reward:.3f}, "
                        f"Cumulative Reward: {cumulative_reward:.3f}, "
                        f"Waiting Time: {total_waiting_time:.2f}, "
                        f"Epsilon: {agent.epsilon:.4f}, "
                        f"Loss: {average_loss:.5f}, "
                        f"Memory: {len(agent.memory)}"
                    )

        finally:
            traci.close()

        if episode % TARGET_UPDATE_EVERY == 0:
            agent.update_target_network()
            print("Target network guncellendi.")

        average_waiting_time = waiting_time_sum_for_episode / max(waiting_time_record_count, 1)
        average_loss = sum(losses) / max(len(losses), 1)

        row = {
            "episode": episode,
            "run_episode": run_episode,
            "total_steps": total_steps,
            "reward": cumulative_reward,
            "average_waiting_time": average_waiting_time,
            "epsilon": agent.epsilon,
            "average_loss": average_loss,
            "memory_size": len(agent.memory),
        }

        append_stats(paths["stats"], row)
        agent.completed_episodes = episode
        agent.save(paths["model"], episode, config["name"])

        print(
            f"\nTotal Episode {episode} bitti. "
            f"Run Episode: {run_episode}/{num_episodes}, "
            f"Episode Reward: {cumulative_reward:.3f}, "
            f"Average Waiting Time: {average_waiting_time:.2f}, "
            f"Epsilon: {agent.epsilon:.4f}, "
            f"Average Loss: {average_loss:.5f}, "
            f"Memory: {len(agent.memory)}"
        )
        print(f"Model kaydedildi: {paths['model']}")

    save_plots(read_stats_history(paths["stats"]), paths["plots"])

    print(f"\nFinal model kaydedildi: {paths['model']}")
    print(f"Istatistikler kaydedildi: {paths['stats']}")
    print(f"Grafikler kaydedildi: {', '.join(paths['plots'])}")


# ============================================
# CLI
# ============================================


def parse_args():
    parser = argparse.ArgumentParser(description="Config tabanli DQL bekleme suresi egitimi")
    parser.add_argument("--config", default="turkis_kavsak", choices=get_config_names())
    parser.add_argument("--episodes", type=int, default=NUM_EPISODES)
    parser.add_argument("--steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--fresh", action="store_true")
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
    os.makedirs(config["output_dir"], exist_ok=True)

    if args.fresh:
        clean_outputs(get_output_paths(config))

    train(
        config=config,
        num_episodes=args.episodes,
        total_steps=args.steps,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
