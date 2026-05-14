import pickle
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
Q_TABLE_FILE = os.path.join(SCRIPT_DIR, "qtable_turkis_actions.pkl")

ACTION_NAMES = {
    0: "MAIN_GREEN",
    1: "TURN_GREEN",
    2: "SIDE_GREEN"
}

with open(Q_TABLE_FILE, "rb") as f:
    Q_table = pickle.load(f)

print("Q-table size:", len(Q_table))

for state, q_values in Q_table.items():
    best_action = int(np.argmax(q_values))

    print(
        "State:", state,
        "Q:", q_values,
        "Best Action:", ACTION_NAMES[best_action]
    )
