import os
import toml

global config
config_path = os.path.join(os.path.dirname(__file__), "config.toml")
with open(file=config_path, mode="r") as fp:
    config = toml.load(fp)
