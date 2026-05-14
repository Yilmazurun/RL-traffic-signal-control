# ============================================
# IMPORTS
# ============================================

import os

# PyTorch bu makinede bazi Intel OpenMP DLL'leri ile cakisabiliyor.
# Egitimin baslayabilmesi icin torch importundan once bu bayrak set edilir.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
import csv
import random
import sys
from collections import deque, namedtuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

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

NUM_EPISODES = 5
TOTAL_STEPS = 12000
DECISION_INTERVAL = 10
MIN_GREEN_STEPS = 20
YELLOW_STEPS = 3

# ============================================
# PHASE INDEXES
# ============================================
# NetEdit phase sirasi:
# 0 = main green
# 1 = main yellow
# 2 = turn green
# 3 = turn yellow
# 4 = side green
# 5 = side yellow

MAIN_GREEN = 0
MAIN_YELLOW = 1

TURN_GREEN = 2
TURN_YELLOW = 3

SIDE_GREEN = 4
SIDE_YELLOW = 5

ACTION_MAIN = 0
ACTION_TURN = 1
ACTION_SIDE = 2

ACTIONS = [ACTION_MAIN, ACTION_TURN, ACTION_SIDE]

ACTION_TO_GREEN_PHASE = {
    ACTION_MAIN: MAIN_GREEN,
    ACTION_TURN: TURN_GREEN,
    ACTION_SIDE: SIDE_GREEN,
}

GREEN_TO_YELLOW_PHASE = {
    MAIN_GREEN: MAIN_YELLOW,
    TURN_GREEN: TURN_YELLOW,
    SIDE_GREEN: SIDE_YELLOW,
}

ACTION_NAMES = {
    ACTION_MAIN: "MAIN_GREEN",
    ACTION_TURN: "TURN_GREEN",
    ACTION_SIDE: "SIDE_GREEN",
}

# ============================================
# DQL PARAMETERS
# ============================================

STATE_SIZE = 6
ACTION_SIZE = len(ACTIONS)

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
REWARD_NORMALIZER = 10.0
SWITCH_PENALTY = 0.5

MODEL_FILE = os.path.join(OUTPUT_DIR, "dql_turkis_model.pth")
STATS_FILE = os.path.join(OUTPUT_DIR, "dql_turkis_stats.csv")
CSV_FIELDS = [
    "episode",
    "run_episode",
    "total_steps",
    "reward",
    "average_queue",
    "epsilon",
    "average_loss",
    "memory_size",
]
PLOT_FILES = [
    os.path.join(OUTPUT_DIR, "dql_episode_reward.png"),
    os.path.join(OUTPUT_DIR, "dql_average_queue.png"),
    os.path.join(OUTPUT_DIR, "dql_epsilon.png"),
]

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

Transition = namedtuple(
    "Transition",
    ("state", "action", "reward", "next_state", "done"),
)

# ============================================
# SUMO HELPER FUNCTIONS
# ============================================


# Mevcut trafik isiginin aktif phase indexini dondurur.
def get_current_phase():
    return traci.trafficlight.getPhase(TLS_ID)


# Trafik isigini verilen phase'e gecirir ve istenirse phase suresini ayarlar.
def set_phase(phase, duration=None):
    traci.trafficlight.setPhase(TLS_ID, phase)

    if duration is not None:
        traci.trafficlight.setPhaseDuration(TLS_ID, duration)


# Verilen lane area detector icindeki arac sayisini dondurur.
def get_queue_length(detector_id):
    return traci.lanearea.getLastStepVehicleNumber(detector_id)


# Verilen detector listesindeki toplam arac sayisini hesaplar.
def get_queue_sum(detectors):
    total = 0

    for detector_id in detectors:
        total += get_queue_length(detector_id)

    return total


# Aktif phase'in hangi action grubuna ait oldugunu dondurur.
def phase_to_action_group(phase):
    if phase in [MAIN_GREEN, MAIN_YELLOW]:
        return ACTION_MAIN

    if phase in [TURN_GREEN, TURN_YELLOW]:
        return ACTION_TURN

    if phase in [SIDE_GREEN, SIDE_YELLOW]:
        return ACTION_SIDE

    return ACTION_MAIN


# ============================================
# STATE AND REWARD
# ============================================


# DQL ajaninin gorecegi sayisal state vektorunu uretir.
# Ilk 3 deger kuyruk yogunluklari, son 3 deger aktif yesil grubunun one-hot bilgisidir.
def get_state():
    main_queue = get_queue_sum(MAIN_DETECTORS) / QUEUE_NORMALIZER
    turn_queue = get_queue_sum(TURN_DETECTORS) / QUEUE_NORMALIZER
    side_queue = get_queue_sum(SIDE_DETECTORS) / QUEUE_NORMALIZER

    current_group = phase_to_action_group(get_current_phase())
    phase_one_hot = np.zeros(3, dtype=np.float32)
    phase_one_hot[current_group] = 1.0

    state = np.array(
        [
            main_queue,
            turn_queue,
            side_queue,
            phase_one_hot[0],
            phase_one_hot[1],
            phase_one_hot[2],
        ],
        dtype=np.float32,
    )

    return np.clip(state, 0.0, 5.0)


# Toplam kuyruga gore negatif reward uretir.
# Gereksiz faz degisimlerini azaltmak icin switch durumunda kucuk ceza eklenir.
def get_reward(action, previous_action):
    total_queue = get_queue_sum(ALL_DETECTORS)
    reward = -float(total_queue) / REWARD_NORMALIZER

    if action != previous_action:
        reward -= SWITCH_PENALTY

    return reward


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
    def __init__(self, device):
        self.device = device
        self.policy_net = DQN(STATE_SIZE, ACTION_SIZE).to(device)
        self.target_net = DQN(STATE_SIZE, ACTION_SIZE).to(device)
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
    def save(self, model_file, episode):
        torch.save(
            {
                "episode": episode,
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
            return random.choice(ACTIONS)

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

    # Kesfi zamanla azaltir, egitimin basinda deneme yapip sonlara dogru daha kararli davranir.
    def decay_epsilon(self):
        self.epsilon = max(EPSILON_MIN, self.epsilon * EPSILON_DECAY)


# ============================================
# APPLY ACTION
# ============================================

last_switch_time = 0


# Secilen action'i trafik isigina uygular.
# Yesilden farkli yesile gecilecekse once ilgili sari faz simule edilir.
def apply_action(action):
    global last_switch_time

    current_phase = get_current_phase()
    target_green_phase = ACTION_TO_GREEN_PHASE[action]

    if current_phase == target_green_phase:
        return

    if current_phase in GREEN_TO_YELLOW_PHASE:
        yellow_phase = GREEN_TO_YELLOW_PHASE[current_phase]
        set_phase(yellow_phase, YELLOW_STEPS)

        for _ in range(YELLOW_STEPS):
            traci.simulationStep()

    set_phase(target_green_phase, 9999)
    last_switch_time = traci.simulation.getTime()


# Minimum yesil suresi doldu mu kontrol eder.
def can_switch():
    current_time = traci.simulation.getTime()
    return current_time - last_switch_time >= MIN_GREEN_STEPS


# ============================================
# SUMO START FUNCTION
# ============================================


# Her episode icin SUMO'yu bastan baslatir.
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
# TRAINING UTILITIES
# ============================================


# Episode sonu metriklerini CSV dosyasina ekler.
def append_stats(row):
    file_exists = os.path.exists(STATS_FILE)
    file_is_empty = (not file_exists) or os.path.getsize(STATS_FILE) == 0

    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
        )

        if file_is_empty:
            writer.writeheader()

        writer.writerow(row)


# CSV icindeki tum episode metriklerini okur; grafikler boylece eklemeli egitimi de gosterir.
def read_stats_history():
    if not os.path.exists(STATS_FILE):
        return []

    history = []

    with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                history.append(
                    {
                        "episode": int(row["episode"]),
                        "reward": float(row["reward"]),
                        "average_queue": float(row["average_queue"]),
                        "epsilon": float(row["epsilon"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

    return history


# Egitim bittikten sonra reward, kuyruk ve epsilon grafiklerini PNG olarak kaydeder.
def save_plots(history):
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
    plt.savefig(PLOT_FILES[0])
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(episodes, [row["average_queue"] for row in history])
    plt.xlabel("Episode")
    plt.ylabel("Average Queue")
    plt.title("DQL Average Queue per Episode")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(PLOT_FILES[1])
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(episodes, [row["epsilon"] for row in history])
    plt.xlabel("Episode")
    plt.ylabel("Epsilon")
    plt.title("DQL Epsilon Decay")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(PLOT_FILES[2])
    plt.close()


# ============================================
# TRAINING LOOP
# ============================================


# Ana egitim dongusu: episode baslatir, action secer, deneyimi memory'ye yazar ve modeli egitir.
def train(num_episodes, total_steps, resume):
    global last_switch_time

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    agent = DQLAgent(device)

    if resume:
        agent.load_if_exists(MODEL_FILE)
    else:
        print("Resume kapali; model sifirdan egitilecek.")

    start_episode = agent.completed_episodes
    end_episode = start_episode + num_episodes

    print("\n=== DQL EPISODE TRAINING STARTED ===")
    print(f"Bu kosuda {num_episodes} episode egitilecek.")
    print(f"Toplam episode araligi: {start_episode + 1}-{end_episode}")

    for run_episode in range(1, num_episodes + 1):
        episode = start_episode + run_episode
        print(
            f"\n========== TOTAL EPISODE {episode}/{end_episode} "
            f"(RUN {run_episode}/{num_episodes}) =========="
        )

        start_sumo_for_episode(episode - 1)

        last_switch_time = 0
        set_phase(MAIN_GREEN, 9999)
        last_switch_time = traci.simulation.getTime()

        cumulative_reward = 0.0
        decision_count = 0
        queue_sum_for_episode = 0.0
        queue_record_count = 0
        losses = []

        previous_action = ACTION_MAIN

        try:
            while traci.simulation.getTime() < total_steps:
                old_state = get_state()

                if can_switch():
                    action = agent.choose_action(old_state)
                else:
                    action = phase_to_action_group(get_current_phase())

                apply_action(action)

                for _ in range(DECISION_INTERVAL):
                    if traci.simulation.getTime() >= total_steps:
                        break
                    traci.simulationStep()

                done = traci.simulation.getTime() >= total_steps
                new_state = get_state()
                reward = get_reward(action, previous_action)

                agent.memory.push(old_state, action, reward, new_state, done)
                loss = agent.optimize_model()

                if loss is not None:
                    losses.append(loss)

                cumulative_reward += reward
                decision_count += 1
                previous_action = action
                agent.decay_epsilon()

                total_queue = get_queue_sum(ALL_DETECTORS)
                queue_sum_for_episode += total_queue
                queue_record_count += 1

                if decision_count % 50 == 0:
                    current_time = int(traci.simulation.getTime())
                    average_loss = sum(losses[-50:]) / max(len(losses[-50:]), 1)

                    print(
                        f"Episode: {episode}, "
                        f"Run Episode: {run_episode}, "
                        f"Time: {current_time}, "
                        f"Action: {ACTION_NAMES[action]}, "
                        f"Reward: {reward:.3f}, "
                        f"Cumulative Reward: {cumulative_reward:.3f}, "
                        f"Queue: {total_queue}, "
                        f"Epsilon: {agent.epsilon:.4f}, "
                        f"Loss: {average_loss:.5f}, "
                        f"Memory: {len(agent.memory)}"
                    )

        finally:
            traci.close()

        if episode % TARGET_UPDATE_EVERY == 0:
            agent.update_target_network()
            print("Target network guncellendi.")

        average_queue = queue_sum_for_episode / max(queue_record_count, 1)
        average_loss = sum(losses) / max(len(losses), 1)

        row = {
            "episode": episode,
            "run_episode": run_episode,
            "total_steps": total_steps,
            "reward": cumulative_reward,
            "average_queue": average_queue,
            "epsilon": agent.epsilon,
            "average_loss": average_loss,
            "memory_size": len(agent.memory),
        }

        append_stats(row)
        agent.completed_episodes = episode
        agent.save(MODEL_FILE, episode)

        print(
            f"\nTotal Episode {episode} bitti. "
            f"Run Episode: {run_episode}/{num_episodes}, "
            f"Episode Reward: {cumulative_reward:.3f}, "
            f"Average Queue: {average_queue:.2f}, "
            f"Epsilon: {agent.epsilon:.4f}, "
            f"Average Loss: {average_loss:.5f}, "
            f"Memory: {len(agent.memory)}"
        )
        print(f"Model kaydedildi: {MODEL_FILE}")

    save_plots(read_stats_history())

    print(f"\nFinal model kaydedildi: {MODEL_FILE}")
    print(f"Istatistikler kaydedildi: {STATS_FILE}")
    print(f"Grafikler kaydedildi: {', '.join(PLOT_FILES)}")


# Yeni bir kosuya temiz baslamak icin DQL cikti dosyalarini siler.
def clean_outputs():
    for file_path in [MODEL_FILE, STATS_FILE] + PLOT_FILES:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Eski cikti silindi: {file_path}")


# Komut satiri parametrelerini okur ve egitimi baslatir.
def parse_args():
    parser = argparse.ArgumentParser(description="Turkis kavsagi icin DQL egitimi")
    parser.add_argument("--episodes", type=int, default=NUM_EPISODES)
    parser.add_argument("--steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.gui:
        USE_GUI = True
        SUMO_BINARY = "sumo-gui"

    if args.fresh:
        clean_outputs()

    train(
        num_episodes=args.episodes,
        total_steps=args.steps,
        resume=not args.no_resume,
    )
