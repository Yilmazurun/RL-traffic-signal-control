import sys

from train_bekleme_suresi import main


if __name__ == "__main__":
    if "--config" not in sys.argv:
        sys.argv.extend(["--config", "yesilyurt_avm_kavsak"])

    main()
