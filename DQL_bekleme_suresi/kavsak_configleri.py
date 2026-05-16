# ============================================
# PATHS
# ============================================

import copy
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
KAVSAK_OUTPUT_ROOT = os.path.join(BASE_DIR, "kavsaklar")
SUMO_CONFIG_FILE = os.path.join(PROJECT_ROOT, "yeni_normal_sure.sumocfg")


# ============================================
# CONFIGS
# ============================================

# Config mantigi:
# - detector_groups: Ajanin state icinde gorecegi detector gruplari.
# - actions: Ajanin secebilecegi yesil fazlar ve bunlarin sari gecis fazlari.
# - 6 fazli kavsaklarda genelde 3 action vardir.
# - 4 fazli gobeklerde genelde 2 action vardir.

KAVSAK_CONFIGS = {
    "turgut_ozal_kavsak": {
        "title": "Turgut Ozal Kavsak",
        "layout": "gobek_6_faz",
        "tls_id": "turgut_ozal_kavsak",
        "output_subdir": "turgut_ozal_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "turgut_b_e_0",
                    "turgut_b_e_1",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "turgut_e_b_0",
                    "turgut_e_b_1",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "turgut_0",
                ],
            },
            {
                "name": "GOBEK_A",
                "detectors": [
                    "turgut_b_e_a_0",
                    "turgut_b_e_a_1",
                ],
            },
            {
                "name": "GOBEK_B",
                "detectors": [
                    "turgut_b_e_b_0",
                    "turgut_b_e_b_1",
                ],
            },
            {
                "name": "GOBEK_C",
                "detectors": [
                    "turgut_b_e_c_0",
                    "turgut_b_e_c_1",
                ],
            },
            {
                "name": "GOBEK_D",
                "detectors": [
                    "turgut_b_e_d_0",
                    "turgut_b_e_d_1",
                ],
            },
        ],
        "actions": [
            {
                "name": "GOBEK_PHASE_0_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "GOBEK_PHASE_2_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "GOBEK_PHASE_4_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "turkis_kavsak": {
        "title": "Turkis Kavsak",
        "layout": "uc_yol_6_faz",
        "tls_id": "turkis_kavsak",
        "output_subdir": "turkis_kavsak",
        "detector_groups": [
            {
                "name": "MAIN",
                "detectors": [
                    "turkis_b_e_0",
                    "turkis_b_e_1",
                    "turkis_e_b_0",
                    "turkis_e_b_1",
                    "turkis_e_b_2",
                ],
            },
            {
                "name": "TURN",
                "detectors": [
                    "turkis_b_e_2",
                ],
            },
            {
                "name": "SIDE",
                "detectors": [
                    "turkis_0",
                    "turkis_1",
                    "turkis_2",
                ],
            },
        ],
        "actions": [
            {
                "name": "MAIN_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "TURN_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "SIDE_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "korfez_kavsak": {
        "title": "Korfez Kavsak",
        "layout": "uc_yol_6_faz",
        "tls_id": "korfez_kavsak",
        "output_subdir": "korfez_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "korfez_b_e_0",
                    "korfez_b_e_1",
                    "korfez_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "korfez_e_b_0",
                    "korfez_e_b_1",
                    "korfez_e_b_2",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "korfez_0",
                    "korfez_1",
                ],
            },
        ],
        "actions": [
            {
                "name": "MAIN_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "TURN_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "SIDE_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "atakent_kavsak": {
        "title": "Atakent Kavsak",
        "layout": "uc_yol_6_faz",
        "tls_id": "atakent_kavsak",
        "output_subdir": "atakent_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "atakent_b_e_0",
                    "atakent_b_e_1",
                    "atakent_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "atakent_e_b_0",
                    "atakent_e_b_1",
                    "atakent_e_b_2",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "atakent_0",
                ],
            },
        ],
        "actions": [
            {
                "name": "MAIN_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "TURN_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "SIDE_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "atakum_lisesi_kavsak": {
        "title": "Atakum Lisesi Kavsak",
        "layout": "gobek_6_faz",
        "tls_id": "atakum_lisesi_kavsak",
        "output_subdir": "atakum_lisesi_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "lise_b_e_0",
                    "lise_b_e_1",
                    "lise_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "lise_e_b_0",
                    "lise_e_b_1",
                    "lise_e_b_2",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "lise_0",
                    "lise_1",
                    "lise_2",
                ],
            },
            {
                "name": "GOBEK_A",
                "detectors": [
                    "lise_b_e_a_0",
                    "lise_b_e_a_1",
                    "lise_b_e_a_2",
                ],
            },
            {
                "name": "GOBEK_B",
                "detectors": [
                    "lise_b_e_b_0",
                    "lise_b_e_b_1",
                    "lise_b_e_b_2",
                ],
            },
            {
                "name": "GOBEK_C",
                "detectors": [
                    "lise_b_e_c_1",
                    "lise_b_e_c_2",
                ],
            },
            {
                "name": "GOBEK_D",
                "detectors": [
                    "lise_b_e_d_0",
                    "lise_b_e_d_1",
                    "lise_b_e_d_2",
                ],
            },
        ],
        "actions": [
            {
                "name": "GOBEK_PHASE_0_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "GOBEK_PHASE_2_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "GOBEK_PHASE_4_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "mimar_sinan_kavsak": {
        "title": "Mimar Sinan Kavsak",
        "layout": "uc_yol_6_faz",
        "tls_id": "mimar_sinan_kavsak",
        "output_subdir": "mimar_sinan_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "mimar_b_e_0",
                    "mimar_b_e_1",
                    "mimar_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "mimar_e_b_0",
                    "mimar_e_b_1",
                    "mimar_e_b_2",
                ],
            },
            {
                "name": "TALI_YOL",
                "detectors": [
                    "mimar_0",
                    "mimar_1",
                ],
            },
        ],
        "actions": [
            {
                "name": "MAIN_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "TURN_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "SIDE_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "omurevleri_kavsak": {
        "title": "Omurevleri Kavsak",
        "layout": "uc_yol_6_faz",
        "tls_id": "omurevleri_kavsak",
        "output_subdir": "omurevleri_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "omurevleri_b_e_0",
                    "omurevleri_b_e_1",
                    "omurevleri_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "omurevleri_e_b_0",
                    "omurevleri_e_b_1",
                    "omurevleri_e_b_2",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "omurevleri_0",
                    "omurevleri_1",
                ],
            },
        ],
        "actions": [
            {
                "name": "MAIN_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "TURN_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "SIDE_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "yenimahalle_gobek": {
        "title": "Yenimahalle Gobek",
        "layout": "gobek_6_faz",
        "tls_id": "yenimahalle_kavsak",
        "output_subdir": "yenimahalle_gobek",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "yenimahalle_b_e_0",
                    "yenimahalle_b_e_1",
                    "yenimahalle_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "yenimahalle_e_b_0",
                    "yenimahalle_e_b_1",
                    "yenimahalle_e_b_2",
                ],
            },
            {
                "name": "YENIMAHALLE_CIKIS",
                "detectors": [
                    "yenimahalle_0",
                    "yenimahalle_1",
                    "yenimahalle_2",
                ],
            },
            {
                "name": "GOBEK_A",
                "detectors": [
                    "yenimahalle_b_e_a_0",
                    "yenimahalle_b_e_a_1",
                    "yenimahalle_b_e_a_2",
                ],
            },
            {
                "name": "GOBEK_B",
                "detectors": [
                    "yenimahalle_b_e_b_0",
                    "yenimahalle_b_e_b_1",
                    "yenimahalle_b_e_b_2",
                ],
            },
            {
                "name": "GOBEK_C",
                "detectors": [
                    "yenimahalle_b_e_c_0",
                    "yenimahalle_b_e_c_1",
                    "yenimahalle_b_e_c_2",
                ],
            },
            {
                "name": "GOBEK_D",
                "detectors": [
                    "yenimahalle_b_e_d_0",
                    "yenimahalle_b_e_d_1",
                    "yenimahalle_b_e_d_2",
                ],
            },
        ],
        "actions": [
            {
                "name": "GOBEK_PHASE_0_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "GOBEK_PHASE_2_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "GOBEK_PHASE_4_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "yesilyurt_avm_kavsak": {
        "title": "Yesilyurt AVM Kavsak",
        "layout": "gobek_6_faz",
        "tls_id": "yesilyurt_avm_kavsak",
        "output_subdir": "yesilyurt_avm_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "yesilyurt_b_e_0",
                    "yesilyurt_b_e_1",
                    "yesilyurt_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "yesilyurt_e_b_0",
                    "yesilyurt_e_b_1",
                    "yesilyurt_e_b_2",
                ],
            },
            {
                "name": "GOBEK_A",
                "detectors": [
                    "yesilyurt_b_e_a_0",
                    "yesilyurt_b_e_a_1",
                    "yesilyurt_b_e_a_2",
                ],
            },
            {
                "name": "GOBEK_B",
                "detectors": [
                    "yesilyurt_b_e_b_0",
                    "yesilyurt_b_e_b_1",
                    "yesilyurt_b_e_b_2",
                ],
            },
            {
                "name": "GOBEK_C",
                "detectors": [
                    "yesilyurt_b_e_c_0",
                    "yesilyurt_b_e_c_1",
                    "yesilyurt_b_e_c_2",
                ],
            },
            {
                "name": "GOBEK_D",
                "detectors": [
                    "yesilyurt_b_e_d_0",
                    "yesilyurt_b_e_d_1",
                ],
            },
        ],
        "actions": [
            {
                "name": "GOBEK_PHASE_0_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "GOBEK_PHASE_2_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "GOBEK_PHASE_4_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
    "pelitkoy_kavsak": {
        "title": "Pelitkoy Kavsak",
        "layout": "gobek_6_faz",
        "tls_id": "pelitkoy_kavsak",
        "output_subdir": "pelitkoy_kavsak",
        "detector_groups": [
            {
                "name": "BATIPARK_ENGIZ",
                "detectors": [
                    "pelitkoy_b_e_0",
                    "pelitkoy_b_e_1",
                    "pelitkoy_b_e_2",
                ],
            },
            {
                "name": "ENGIZ_BATIPARK",
                "detectors": [
                    "pelitkoy_e_b_0",
                    "pelitkoy_e_b_1",
                    "pelitkoy_e_b_2",
                ],
            },
            {
                "name": "YAN_YOL_GIRIS",
                "detectors": [
                    "pelitkoy_0",
                    "pelitkoy_1",
                ],
            },
            {
                "name": "GOBEK_A",
                "detectors": [
                    "pelitkoy_b_e_a_0",
                    "pelitkoy_b_e_a_1",
                    "pelitkoy_b_e_a_2",
                ],
            },
            {
                "name": "GOBEK_B",
                "detectors": [
                    "pelitkoy_b_e_b_0",
                    "pelitkoy_b_e_b_1",
                    "pelitkoy_b_e_b_2",
                ],
            },
            {
                "name": "GOBEK_C",
                "detectors": [
                    "pelitkoy_b_e_c_1",
                    "pelitkoy_b_e_c_2",
                ],
            },
            {
                "name": "GOBEK_D",
                "detectors": [
                    "pelitkoy_b_e_d_0",
                    "pelitkoy_b_e_d_1",
                    "pelitkoy_b_e_d_2",
                ],
            },
        ],
        "actions": [
            {
                "name": "GOBEK_PHASE_0_GREEN",
                "green_phase": 0,
                "yellow_phase": 1,
            },
            {
                "name": "GOBEK_PHASE_2_GREEN",
                "green_phase": 2,
                "yellow_phase": 3,
            },
            {
                "name": "GOBEK_PHASE_4_GREEN",
                "green_phase": 4,
                "yellow_phase": 5,
            },
        ],
    },
}


def get_config(config_name):
    if config_name not in KAVSAK_CONFIGS:
        available = ", ".join(sorted(KAVSAK_CONFIGS))
        raise ValueError(f"Bilinmeyen config: {config_name}. Secenekler: {available}")

    config = copy.deepcopy(KAVSAK_CONFIGS[config_name])
    config["name"] = config_name
    config["project_root"] = PROJECT_ROOT
    config["sumo_config_file"] = SUMO_CONFIG_FILE
    config["output_dir"] = os.path.join(KAVSAK_OUTPUT_ROOT, config["output_subdir"])
    return config


def get_config_names():
    return sorted(KAVSAK_CONFIGS.keys())
