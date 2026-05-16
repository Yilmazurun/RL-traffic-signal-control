import sys

from train_bekleme_suresi import main


if __name__ == "__main__":
    if "--config" not in sys.argv:
        sys.argv.extend(["--config", "mimar_sinan_kavsak"])

    main()
