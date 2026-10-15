"""Koridor DQN egitimi: 10 ajan tek simulasyonda birlikte egitilir.

Parca parca calistirilabilir. Her bolum sonunda tum durum (aglar, optimizer,
deneyim bellegi, epsilon, bolum sayisi) egitimler/<kosu>/checkpoint.pt dosyasina
yazilir; ayni komut tekrar calistirilinca kaldigi yerden devam eder.

Ornekler (PowerShell, proje kokunden):
    python DQL_koridor\\train_koridor.py --run ana --episodes 3
    python DQL_koridor\\train_koridor.py --run ana --episodes 3      # devam eder
    python DQL_koridor\\train_koridor.py --run ablasyon_kalkansiz --no-shield --episodes 3

Erken durdurmak icin: Ctrl+C (yarim bolum kaydedilmez, son tam bolumden devam edilir)
veya egitimler\\<kosu>\\DUR adli bos bir dosya olustur (mevcut bolum bitince durur).
"""
import argparse
import csv
import json
import os
import random
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import koridor_ajan as ka  # noqa: E402

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

traci = ka.traci

NET_FILE = ka.PROJECT_ROOT / "yeni_normal_sure.net.xml"
ROUTE_FILE = ka.PROJECT_ROOT / "arac_talepleri" / "deneme_1.rou.xml"
BASE_DETECTOR_FILE = ka.PROJECT_ROOT / "Detectors" / "detector_deneme.add.xml"

# Talep 12000 s'de bitiyor ama giris kuyrugu ~17000-19000 s'ye kadar bosaliyor.
# Bolum bu donemi de kapsar (eski egitimde 12000 s idi).
EPISODE_STEPS = 19000
# Olcumdeki tohumlar (1-5) ile cakismasin.
TRAIN_SEED_OFFSET = 1000

GAMMA = 0.95
LEARNING_RATE = 5e-4
BATCH_SIZE = 64
MEMORY_SIZE = 50000
MIN_REPLAY_SIZE = 1000
TARGET_UPDATE_STEPS = 1000

# Epsilon bolum basina azalir (eski egitimde karar basina azaliyordu ve
# ilk bolumun yarisinda 0.05'e iniyordu).
EPSILON_START = 1.0
EPSILON_MIN = 0.05
EPSILON_DECAY_PER_EPISODE = 0.85

LOG_FIELDS = [
    "episode",
    "seed",
    "epsilon",
    "sim_end_time",
    "wall_clock_s",
    "arrived",
    "mean_travel_time",
    "teleports",
    "emergency_stops",
    "mean_reward",
    "mean_wait_part",
    "mean_pressure_part",
    "mean_starve_part",
    "overrides",
    "mean_loss",
]


class ReplayBuffer:
    def __init__(self, capacity, state_size):
        self.capacity = capacity
        self.states = np.zeros((capacity, state_size), dtype=np.float32)
        self.next_states = np.zeros((capacity, state_size), dtype=np.float32)
        self.actions = np.zeros(capacity, dtype=np.int64)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.size = 0

    def push(self, state, action, reward, next_state, done):
        i = self.position
        self.states[i] = state
        self.actions[i] = action
        self.rewards[i] = reward
        self.next_states[i] = next_state
        self.dones[i] = done
        self.position = (i + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size):
        idx = np.random.randint(0, self.size, size=batch_size)
        return self.states[idx], self.actions[idx], self.rewards[idx], self.next_states[idx], self.dones[idx]

    def state_dict(self):
        n = self.size
        return {
            "states": self.states[:n].copy() if n < self.capacity else self.states.copy(),
            "next_states": self.next_states[:n].copy() if n < self.capacity else self.next_states.copy(),
            "actions": self.actions[:n].copy() if n < self.capacity else self.actions.copy(),
            "rewards": self.rewards[:n].copy() if n < self.capacity else self.rewards.copy(),
            "dones": self.dones[:n].copy() if n < self.capacity else self.dones.copy(),
            "position": self.position,
            "size": self.size,
        }

    def load_state_dict(self, data):
        n = data["size"]
        self.states[:n] = data["states"][:n]
        self.next_states[:n] = data["next_states"][:n]
        self.actions[:n] = data["actions"][:n]
        self.rewards[:n] = data["rewards"][:n]
        self.dones[:n] = data["dones"][:n]
        self.position = data["position"]
        self.size = n


class Learner:
    """Bir ajanin ogrenme parcasi: Double DQN, Huber kaybi, sert hedef guncellemesi."""

    def __init__(self, agent, device):
        self.agent = agent
        self.device = device
        self.policy = ka.QNetwork(agent.state_size, agent.action_size).to(device)
        self.target = ka.QNetwork(agent.state_size, agent.action_size).to(device)
        self.target.load_state_dict(self.policy.state_dict())
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=LEARNING_RATE)
        self.memory = ReplayBuffer(MEMORY_SIZE, agent.state_size)
        self.grad_steps = 0
        agent.policy = self.policy
        agent.device = device

    def choose(self, state, epsilon):
        if random.random() < epsilon:
            return random.randrange(self.agent.action_size)
        return self.agent.greedy_action(state)

    def optimize(self):
        if self.memory.size < MIN_REPLAY_SIZE:
            return None

        s, a, r, s2, d = self.memory.sample(BATCH_SIZE)
        s = torch.from_numpy(s).to(self.device)
        a = torch.from_numpy(a).to(self.device)
        r = torch.from_numpy(r).to(self.device)
        s2 = torch.from_numpy(s2).to(self.device)
        d = torch.from_numpy(d).to(self.device)

        q = self.policy(s).gather(1, a.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            next_action = self.policy(s2).argmax(dim=1, keepdim=True)
            next_q = self.target(s2).gather(1, next_action).squeeze(1)
            target = r + GAMMA * next_q * (1.0 - d)

        loss = F.smooth_l1_loss(q, target)
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 10.0)
        self.optimizer.step()

        self.grad_steps += 1
        if self.grad_steps % TARGET_UPDATE_STEPS == 0:
            self.target.load_state_dict(self.policy.state_dict())

        return float(loss.item())

    def state_dict(self):
        return {
            "policy": self.policy.state_dict(),
            "target": self.target.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "memory": self.memory.state_dict(),
            "grad_steps": self.grad_steps,
        }

    def load_state_dict(self, data):
        self.policy.load_state_dict(data["policy"])
        self.target.load_state_dict(data["target"])
        self.optimizer.load_state_dict(data["optimizer"])
        self.memory.load_state_dict(data["memory"])
        self.grad_steps = data["grad_steps"]


def write_detector_file(run_dir):
    out_dir = run_dir / "detector_ciktilari"
    out_dir.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(BASE_DETECTOR_FILE)
    for element in tree.getroot().iter():
        if element.get("id") and element.get("file") is not None:
            element.set("file", f"detector_ciktilari/{element.get('id')}.xml")
    add_file = run_dir / "detector_egitim.add.xml"
    tree.write(add_file, encoding="utf-8", xml_declaration=True)
    return add_file


def start_sumo(seed, add_file):
    traci.start(
        [
            "sumo",
            "-n", str(NET_FILE),
            "-r", str(ROUTE_FILE),
            "-a", str(add_file),
            "--step-length", "1",
            "--lateral-resolution", "0",
            "--seed", str(seed),
            "--no-step-log", "true",
            "--duration-log.disable", "true",
            "--no-warnings", "true",
        ]
    )


def save_checkpoint(run_dir, episode, settings, learners, rng_state):
    data = {
        "episode": episode,
        "settings": settings,
        "learners": {name: learner.state_dict() for name, learner in learners.items()},
        "rng": rng_state,
    }
    tmp = run_dir / "checkpoint.pt.tmp"
    torch.save(data, tmp)
    os.replace(tmp, run_dir / "checkpoint.pt")

    # Olcum icin yalnizca agirliklar (kucuk dosya); her 5 bolumde bir de kopya.
    models = {
        "episode": episode,
        "settings": settings,
        "policies": {name: learner.policy.state_dict() for name, learner in learners.items()},
    }
    tmp = run_dir / "modeller.pt.tmp"
    torch.save(models, tmp)
    os.replace(tmp, run_dir / "modeller.pt")
    if episode % 5 == 0:
        torch.save(models, run_dir / f"modeller_bolum_{episode:03d}.pt")


def append_log(run_dir, row):
    log_file = run_dir / "egitim_log.csv"
    new = not log_file.exists()
    with log_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def run_episode(episode, agents, learners, epsilon, add_file, max_steps):
    seed = TRAIN_SEED_OFFSET + episode
    start_sumo(seed, add_file)
    wall_start = time.time()

    for agent in agents:
        agent.initialize()
        agent.override_count = 0

    pending = {agent.config["name"]: None for agent in agents}
    rewards, waits, pressures, starves, losses = [], [], [], [], []
    depart_times = {}
    travel_times = []
    teleports = 0
    emergency_stops = 0

    while traci.simulation.getTime() < max_steps:
        now = traci.simulation.getTime()

        for agent in agents:
            agent.update(now)

        for agent in agents:
            if not agent.at_decision_point(now):
                continue

            name = agent.config["name"]
            learner = learners[name]
            state = agent.get_state(now)

            if pending[name] is not None:
                prev_state, prev_action, switched = pending[name]
                reward, parts = agent.reward(now, switched)
                learner.memory.push(prev_state, prev_action, reward, state, 0.0)
                rewards.append(reward)
                waits.append(parts["wait"])
                pressures.append(parts["pressure"])
                starves.append(parts["starve"])
                loss = learner.optimize()
                if loss is not None:
                    losses.append(loss)

            proposed = learner.choose(state, epsilon)
            action = agent.shield(proposed, now)
            switched = agent.apply(action, now)
            # Kalkan degistirdiyse gercekte uygulanan action ogrenilir.
            pending[name] = (state, action, switched)

        traci.simulationStep()
        sim_now = traci.simulation.getTime()

        for vehicle_id in traci.simulation.getDepartedIDList():
            depart_times[vehicle_id] = sim_now
        for vehicle_id in traci.simulation.getArrivedIDList():
            if vehicle_id in depart_times:
                travel_times.append(sim_now - depart_times.pop(vehicle_id))
        teleports += traci.simulation.getStartingTeleportNumber()
        try:
            emergency_stops += traci.simulation.getEmergencyStoppingVehiclesNumber()
        except (AttributeError, traci.TraCIException):
            pass

        if int(sim_now) % 1000 == 0:
            print(
                f"  bolum {episode} t={int(sim_now)} varan={len(travel_times)} "
                f"isinlanma={teleports} odul_ort={np.mean(rewards[-500:]) if rewards else 0:.3f}",
                flush=True,
            )

        if traci.simulation.getMinExpectedNumber() == 0:
            break

    end_time = traci.simulation.getTime()
    traci.close()

    return {
        "episode": episode,
        "seed": seed,
        "epsilon": f"{epsilon:.3f}",
        "sim_end_time": int(end_time),
        "wall_clock_s": round(time.time() - wall_start),
        "arrived": len(travel_times),
        "mean_travel_time": f"{np.mean(travel_times):.2f}" if travel_times else "",
        "teleports": teleports,
        "emergency_stops": emergency_stops,
        "mean_reward": f"{np.mean(rewards):.4f}" if rewards else "",
        "mean_wait_part": f"{np.mean(waits):.4f}" if waits else "",
        "mean_pressure_part": f"{np.mean(pressures):.4f}" if pressures else "",
        "mean_starve_part": f"{np.mean(starves):.4f}" if starves else "",
        "overrides": sum(agent.override_count for agent in agents),
        "mean_loss": f"{np.mean(losses):.4f}" if losses else "",
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Koridor DQN egitimi (parca parca calistirilabilir)")
    parser.add_argument("--run", default="ana", help="Kosu adi; egitimler/<kosu>/ altina kaydedilir.")
    parser.add_argument("--episodes", type=int, default=1, help="Bu oturumda calisacak bolum sayisi.")
    parser.add_argument("--max-steps", type=int, default=EPISODE_STEPS)
    parser.add_argument("--reward", choices=["combo", "wait"], help="Odul turu (yeni kosu icin).")
    parser.add_argument("--no-shield", action="store_true", help="Azami kirmizi kalkanini kapat.")
    parser.add_argument("--no-neighbors", action="store_true", help="Komsu kavsak bilgisini kapat.")
    parser.add_argument("--no-red-age", action="store_true", help="Kirmizi yasi bilgisini kapat.")
    parser.add_argument("--no-moving", action="store_true", help="Duran/hareketli ayrimini kapat.")
    parser.add_argument("--cpu", action="store_true", help="GPU varsa bile CPU kullan.")
    return parser.parse_args()


def build_settings(args):
    settings = dict(ka.DEFAULT_SETTINGS)
    if args.reward:
        settings["reward"] = args.reward
    if args.no_shield:
        settings["shield"] = False
    if args.no_neighbors:
        settings["neighbors"] = False
    if args.no_red_age:
        settings["red_age"] = False
    if args.no_moving:
        settings["moving"] = False
    return settings


def main():
    args = parse_args()
    run_dir = ka.RUNS_DIR / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = run_dir / "checkpoint.pt"
    stop_file = run_dir / "DUR"
    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda")

    if checkpoint_file.exists():
        checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
        settings = checkpoint["settings"]
        start_episode = checkpoint["episode"] + 1
        requested = build_settings(args)
        if requested != settings and any(
            [args.reward, args.no_shield, args.no_neighbors, args.no_red_age, args.no_moving]
        ):
            sys.exit(
                f"Bu kosu farkli ayarlarla baslatilmis: {settings}\n"
                "Ayarlari degistirmek icin yeni bir --run adi kullan."
            )
        print(f"Devam ediliyor: {args.run}, bolum {start_episode}'den")
    else:
        checkpoint = None
        settings = build_settings(args)
        start_episode = 1
        (run_dir / "ayarlar.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
        print(f"Yeni kosu: {args.run}")

    print(f"Ayarlar: {settings}")
    print(f"Cihaz: {device}")

    agents = [ka.KoridorAgent(config, settings) for config in ka.load_configs()]
    ka.link_neighbors(agents)
    learners = {agent.config["name"]: Learner(agent, device) for agent in agents}

    if checkpoint is not None:
        for name, data in checkpoint["learners"].items():
            learners[name].load_state_dict(data)
        rng = checkpoint.get("rng")
        if rng:
            random.setstate(rng["python"])
            np.random.set_state(rng["numpy"])
            torch.set_rng_state(rng["torch"].cpu())

    add_file = write_detector_file(run_dir)
    end_episode = start_episode + args.episodes - 1

    for episode in range(start_episode, end_episode + 1):
        if stop_file.exists():
            print("DUR dosyasi bulundu, egitim durduruldu.")
            stop_file.unlink()
            break

        epsilon = max(EPSILON_MIN, EPSILON_START * EPSILON_DECAY_PER_EPISODE ** (episode - 1))
        print(f"\n=== {args.run}: bolum {episode} (epsilon {epsilon:.3f}) ===", flush=True)

        try:
            row = run_episode(episode, agents, learners, epsilon, add_file, args.max_steps)
        except KeyboardInterrupt:
            try:
                traci.close()
            except Exception:
                pass
            print(f"Durduruldu. Bolum {episode} kaydedilmedi; son kayit bolum {episode - 1}.")
            return

        rng_state = {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state()}
        save_checkpoint(run_dir, episode, settings, learners, rng_state)
        append_log(run_dir, row)
        print(
            f"Bolum {episode} bitti ({row['wall_clock_s']} s): varan {row['arrived']}, "
            f"ort. seyahat {row['mean_travel_time']} s, isinlanma {row['teleports']}, "
            f"acil durus {row['emergency_stops']}, odul {row['mean_reward']}, kalkan mudahale {row['overrides']}",
            flush=True,
        )

    print(f"\nKayit: {checkpoint_file}")


if __name__ == "__main__":
    main()
