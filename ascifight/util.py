import os
import structlog
import toml

absolute_path = os.path.dirname(__file__)
with open(f"{absolute_path}/config.toml", mode="r") as fp:
    config = toml.load(fp)


time_stamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False)
pre_chain = [
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    # Add extra attributes of LogRecord objects to the event dictionary
    # so that values passed in the extra parameter of log methods pass
    # through to log output.
    structlog.stdlib.ExtraAdder(),
    time_stamper,
]

log_config_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.contextvars.merge_contextvars,
                structlog.processors.JSONRenderer(sort_keys=True),
            ],
            "foreign_pre_chain": pre_chain,
        },
        "colored": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processors": [
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            "foreign_pre_chain": pre_chain,
        },
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "colored",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{config['server']['log_dir']}/game.log",
            "backupCount": 100,
            "formatter": "plain",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

flag_icon = "\u25B2"
base_icon = "\u25D9"
wall_icon = "\u2588\u2588\u2588"

colors = {
    0: "\u001b[31m",
    1: "\u001b[32m",
    2: "\u001b[33m",
    3: "\u001b[34m",
    4: "\u001b[35m",
    5: "\u001b[36m",
    "bold": "\033[1m",
    "revert": "\x1b[0m",
}

color_names = {
    0: "red",
    1: "green",
    2: "yellow",
    3: "blue",
    4: "purple",
    5: "cyan",
}

color_rgb_mapping = {
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "purple": (128, 0, 128),
    "cyan": (0, 100, 100),
}

api_description = """
**ASCI-Fight** allows you to fight with your teammates in style.

The goal of this game is to score as many points as possible by capturing your enemies flags. Go to your enemies bases, 
grab the flags and put them on top of your own base.Any enemies that try to stop you, you can attack. Of course they will 
respawn, but the won't bother you in the next ticks.

Show your coding prowess by creating the best scripts and dominate your co-workers!

## The Game 

You control a couple of actors with different properties to rule the field of battle. Depending on their properties they 
can perform various orders for you. Once the server is up (which must be the case, because you can read this documentation)
there is a grace period before the game starts. Once it has started you can give orders for a certain time, then all orders are 
executed at once and the game is waiting for the next orders.


The _game_start_ service tells you when the next game is starting.


The game ends after a certain number of points were scored or a certain number of ticks have passed.

## Components

Whats in the game you ask? Easy!

### Actors

Actors are your minions you move over the field of battle. They have different properties like _grab_ and _attack_. The can perform _orders_ to move, attack and grab.

### Bases

Each team has one. Thats where your actor start, where your flag sits and were both your actors and your flag return when they are killed or the flag is scored by an enemy team.

### Flags

There is a flag in each base. Your actor can grab it, pass it to another actor, throw it down or capture it in your own base to score!

### Walls

You, and your actors, cant walk through these!

## Orders

You can perform a couple of orders do reach your goals of co-worker domination. Orders are executed in the order (no pun intended) 
below. 
But beware, each _actor_ can only carry out each order only once per game tick.

### Move Order

With a move order you can move around any of your _actors_, by exactly one field in any non-diagonal direction. 

It is not allowed to step on fields:

* **contain another actor**
* **contain a base**
* **contain a wall field**

If an _actor_ moves over the flag of its own team, the flag is returned to its base!

### GrabPut Order

If an _actor_ does not have the flag, it can grab it with this order. Give it a direction from its current position and it will try to grab
the _flag_ from the target field. 

If an _actor_ does have the flag it can put it into a target field. This target field can be empty or contain an _actor_, but not a wall.
If the target field contains an _actor_ that can not carry the flag (_grab_ property is zero) this will not work. If an _actor_ puts a an enemy flag
on its on base, while the flag is at home, you **score**!


GrabPut actions only have a certain probability to work. If the _grab_ property of an _actor_ is smaller than 1, grabbing or putting might not succeed always.


Only _actors_ with a non-zero _grab_ property can _grabput_.

### Attack Order

With attack orders you can force other actors, even your own, to respawn near their base. Just hit them and they are gone.


Attack actions only have a certain probability to work. If the _attack_ property of an _actor_ is smaller than 1, attacking might not succeed always.

Only _actors_ with a non-zero _attack_ property can _attack_.

### Destroy Order

Destroy orders you can remove those pesky walls. Just walk up to them and target the next wall with a destroy order.


Destroy actions only have a certain probability to work. If the _destroy_ property of an _actor_ is smaller than 1, destroying might not succeed always.

Only _actors_ with a non-zero _destroy_ property can _destroy_.

### Build Order

Build orders can get you more walls where you want them. Walk next to the location where you want a wall and then start building.


Build actions only have a certain probability to work. If the _build_ property of an _actor_ is smaller than 1, building might not succeed always.

Only _actors_ with a non-zero _build_ property can _build_.

## States

To act you need to know things. ASCI fight is a perfect information game. So you can directly see what you need to do and what your actions have caused.

### Game State

This gets you the current state of the game. The position of each game component is something you can find here. Also other information like the current tick and such.

### Game Rules

This section is static per game and tells you what each actor can do, if the flag needs to be at home to score, what the maximum score or tick number is and other static information.

### Game Timing

Here you get the current tick and when the next tick executes both on absolute time and time-deltas. This is more lightweight than the _Game State_ an can be queried often. 

## Logistics

### Log Files

This service tells you which log files are available. 'game.log' is always the log file of the current game. Others get a number attached.

You can fetch log files through the '/logs/[filename]' endpoint.

## Image

Fetch a png image of the current state of the game!

"""
