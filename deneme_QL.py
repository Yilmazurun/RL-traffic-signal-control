# ============================================
# IMPORTS
# ============================================

import os
import sys
import random
import pickle
import numpy as np
import matplotlib.pyplot as plt

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

USE_GUI = False   # Eğitim için False, izlemek istersen True yap

SUMO_BINARY = "sumo-gui" if USE_GUI else "sumo"

# ============================================
# GENERAL SETTINGS
# ============================================

TLS_ID = "turkis_kavsak"

NUM_EPISODES = 20             # Kaç kere baştan simülasyon çalışacak
TOTAL_STEPS = 12000           # Her episode kaç simülasyon saniyesi sürecek
DECISION_INTERVAL = 10        # 10 saniyede bir karar
MIN_GREEN_STEPS = 20          # minimum 20 saniye yeşil
YELLOW_STEPS = 3              # sarı faz süresi

# ============================================
# PHASE INDEXES
# ============================================
# NetEdit phase sırası buna göre olmalı:
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
    ACTION_SIDE: SIDE_GREEN
}

GREEN_TO_YELLOW_PHASE = {
    MAIN_GREEN: MAIN_YELLOW,
    TURN_GREEN: TURN_YELLOW,
    SIDE_GREEN: SIDE_YELLOW
}

ACTION_NAMES = {
    ACTION_MAIN: "MAIN_GREEN",
    ACTION_TURN: "TURN_GREEN",
    ACTION_SIDE: "SIDE_GREEN"
}

# ============================================
# RL PARAMETERS
# ============================================

ALPHA = 0.1
GAMMA = 0.9

EPSILON = 0.3
EPSILON_MIN = 0.02
EPSILON_DECAY = 0.99995

Q_TABLE_FILE = "qtable_turkis_actions.pkl"

# ============================================
# DETECTORS
# ============================================

MAIN_DETECTORS = [
    "turkis_b_e_0",
    "turkis_b_e_1",
    "turkis_e_b_0",
    "turkis_e_b_1",
    "turkis_e_b_2"
]

TURN_DETECTORS = [
    "turkis_b_e_2"
]

SIDE_DETECTORS = [
    "turkis_0",
    "turkis_1",
    "turkis_2"
]

ALL_DETECTORS = MAIN_DETECTORS + TURN_DETECTORS + SIDE_DETECTORS

# ============================================
# Q TABLE LOAD
# ============================================

if os.path.exists(Q_TABLE_FILE):
    with open(Q_TABLE_FILE, "rb") as f:
        Q_table = pickle.load(f)
    print(f"Q-table yüklendi: {Q_TABLE_FILE}")
else:
    Q_table = {}
    print("Yeni Q-table oluşturuldu.")

# ============================================
# HELPER FUNCTIONS
# ============================================

# Mevcut trafik ışığının aktif phase indexini döndürür.
def get_current_phase():
    return traci.trafficlight.getPhase(TLS_ID)


# Trafik ışığını verilen phase'e geçirir.
def set_phase(phase, duration=None):
    traci.trafficlight.setPhase(TLS_ID, phase)

    if duration is not None:
        traci.trafficlight.setPhaseDuration(TLS_ID, duration)


# Verilen detector içindeki araç sayısını döndürür.
def get_queue_length(detector_id):
    return traci.lanearea.getLastStepVehicleNumber(detector_id)


# Verilen detector listesindeki toplam araç sayısını hesaplar.
def get_queue_sum(detectors):
    total = 0

    for detector_id in detectors:
        total += get_queue_length(detector_id)

    return total


# Araç sayısını küçük state kategorilerine ayırır.
def discretize(q):
    if q <= 5:
        return 0
    elif q <= 15:
        return 1
    elif q <= 30:
        return 2
    else:
        return 3


# Aktif phase'in hangi action grubuna ait olduğunu döndürür.
def phase_to_action_group(phase):
    if phase in [MAIN_GREEN, MAIN_YELLOW]:
        return ACTION_MAIN

    if phase in [TURN_GREEN, TURN_YELLOW]:
        return ACTION_TURN

    if phase in [SIDE_GREEN, SIDE_YELLOW]:
        return ACTION_SIDE

    return ACTION_MAIN


# ============================================
# STATE
# ============================================

# RL ajanının göreceği state bilgisini üretir.
def get_state():
    main_queue = get_queue_sum(MAIN_DETECTORS)
    turn_queue = get_queue_sum(TURN_DETECTORS)
    side_queue = get_queue_sum(SIDE_DETECTORS)

    main_queue = discretize(main_queue)
    turn_queue = discretize(turn_queue)
    side_queue = discretize(side_queue)

    current_group = phase_to_action_group(get_current_phase())

    return (
        main_queue,
        turn_queue,
        side_queue,
        current_group
    )


# ============================================
# REWARD
# ============================================

# Toplam kuyruğa göre negatif reward üretir.
def get_reward():
    total_queue = get_queue_sum(ALL_DETECTORS)

    return -float(total_queue)


# ============================================
# Q FUNCTIONS
# ============================================

# State Q-table içinde yoksa oluşturur.
def ensure_state_exists(state):
    if state not in Q_table:
        Q_table[state] = np.zeros(len(ACTIONS))

    if len(Q_table[state]) != len(ACTIONS):
        Q_table[state] = np.zeros(len(ACTIONS))


# Verilen state için en yüksek Q değerini döndürür.
def get_max_q(state):
    ensure_state_exists(state)
    return np.max(Q_table[state])


# Epsilon-greedy yöntemle action seçer.
def choose_action(state, epsilon):
    ensure_state_exists(state)

    if random.random() < epsilon:
        return random.choice(ACTIONS)

    return int(np.argmax(Q_table[state]))


# Q-learning formülüne göre Q-table'ı günceller.
def update_q_table(old_state, action, reward, new_state):
    ensure_state_exists(old_state)
    ensure_state_exists(new_state)

    old_q = Q_table[old_state][action]
    future_q = get_max_q(new_state)

    new_q = old_q + ALPHA * (
        reward + GAMMA * future_q - old_q
    )

    Q_table[old_state][action] = new_q


# ============================================
# APPLY ACTION
# ============================================

last_switch_time = 0


# Seçilen action'ı trafik ışığına uygular.
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


# Minimum yeşil süresi doldu mu kontrol eder.
def can_switch():
    current_time = traci.simulation.getTime()
    return current_time - last_switch_time >= MIN_GREEN_STEPS


# ============================================
# SUMO START FUNCTION
# ============================================

# Her episode için SUMO'yu baştan başlatır.
def start_sumo_for_episode(episode_number):
    sumo_config = [
        SUMO_BINARY,
        "-c", "yeni_normal_sure.sumocfg",
        "--step-length", "1",
        "--lateral-resolution", "0",
        "--seed", str(episode_number + 1)
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
# TRAINING HISTORY
# ============================================

episode_history = []
episode_reward_history = []
episode_average_queue_history = []
epsilon_history = []

# ============================================
# EPISODE TRAINING LOOP
# ============================================

print("\n=== EPISODE TRAINING STARTED ===")

for episode in range(NUM_EPISODES):

    print(f"\n========== EPISODE {episode + 1}/{NUM_EPISODES} ==========")

    start_sumo_for_episode(episode)

    last_switch_time = 0

    set_phase(MAIN_GREEN, 9999)
    last_switch_time = traci.simulation.getTime()

    cumulative_reward = 0.0
    decision_count = 0
    queue_sum_for_episode = 0.0
    queue_record_count = 0

    while traci.simulation.getTime() < TOTAL_STEPS:

        old_state = get_state()

        if can_switch():
            action = choose_action(old_state, EPSILON)
        else:
            action = phase_to_action_group(get_current_phase())

        apply_action(action)

        for _ in range(DECISION_INTERVAL):
            if traci.simulation.getTime() >= TOTAL_STEPS:
                break
            traci.simulationStep()

        new_state = get_state()
        reward = get_reward()

        cumulative_reward += reward

        update_q_table(
            old_state,
            action,
            reward,
            new_state
        )

        decision_count += 1

        EPSILON = max(EPSILON_MIN, EPSILON * EPSILON_DECAY)

        total_queue = get_queue_sum(ALL_DETECTORS)
        queue_sum_for_episode += total_queue
        queue_record_count += 1

        if decision_count % 50 == 0:
            current_time = int(traci.simulation.getTime())

            print(
                f"Episode: {episode + 1}, "
                f"Time: {current_time}, "
                f"State: {old_state}, "
                f"Action: {ACTION_NAMES[action]}, "
                f"Reward: {reward}, "
                f"Cumulative Reward: {cumulative_reward}, "
                f"Queue: {total_queue}, "
                f"Epsilon: {EPSILON:.4f}, "
                f"Q: {Q_table[old_state]}"
            )

    average_queue = queue_sum_for_episode / max(queue_record_count, 1)

    episode_history.append(episode + 1)
    episode_reward_history.append(cumulative_reward)
    episode_average_queue_history.append(average_queue)
    epsilon_history.append(EPSILON)

    print(
        f"\nEpisode {episode + 1} bitti. "
        f"Episode Reward: {cumulative_reward}, "
        f"Average Queue: {average_queue:.2f}, "
        f"Epsilon: {EPSILON:.4f}, "
        f"Q-table size: {len(Q_table)}"
    )

    with open(Q_TABLE_FILE, "wb") as f:
        pickle.dump(Q_table, f)

    print(f"Q-table kaydedildi: {Q_TABLE_FILE}")

    traci.close()

# ============================================
# FINAL SAVE
# ============================================

with open(Q_TABLE_FILE, "wb") as f:
    pickle.dump(Q_table, f)

print(f"\nFinal Q-table kaydedildi: {Q_TABLE_FILE}")
print("Final Q-table size:", len(Q_table))

# ============================================
# PLOTS
# ============================================

plt.figure(figsize=(10, 5))
plt.plot(episode_history, episode_reward_history)
plt.xlabel("Episode")
plt.ylabel("Cumulative Reward")
plt.title("Episode Reward")
plt.grid(True)
plt.show()

plt.figure(figsize=(10, 5))
plt.plot(episode_history, episode_average_queue_history)
plt.xlabel("Episode")
plt.ylabel("Average Queue")
plt.title("Average Queue per Episode")
plt.grid(True)
plt.show()

plt.figure(figsize=(10, 5))
plt.plot(episode_history, epsilon_history)
plt.xlabel("Episode")
plt.ylabel("Epsilon")
plt.title("Epsilon Decay")
plt.grid(True)
plt.show()