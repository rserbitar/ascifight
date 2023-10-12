import os
import toml
import httpx
import structlog
import logging.config

from ascifight.board.actions import Directions
import ascifight.routers.states

global config
absolute_path = os.path.dirname(__file__)
with open(file=f"{absolute_path}/client_config.toml", mode="r") as fp:
    config = toml.load(fp)

try:
    os.mkdir(config["log_dir"])
except FileExistsError:
    pass


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
    "disable_existing_loggers": True,
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
            "filename": f"{config['log_dir']}/game.log",
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

logging.config.dictConfig(log_config_dict)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        time_stamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.getLogger()


def get_game_state() -> ascifight.routers.states.StateResponse:
    url = config["server"] + "states/game_state"
    response = httpx.get(url)
    return ascifight.routers.states.StateResponse.model_validate(response.json())


def get_current_actions() -> ascifight.routers.states.CurrentActionsResponse:
    url = config["server"] + "states/current_actions"
    response = httpx.get(url)
    return ascifight.routers.states.CurrentActionsResponse.model_validate(
        response.json()
    )


def get_all_actions() -> ascifight.routers.states.AllActionsResponse:
    url = config["server"] + "states/all_actions"
    response = httpx.get(url)
    return ascifight.routers.states.AllActionsResponse.model_validate(response.json())


def get_game_rules() -> ascifight.routers.states.RulesResponse:
    url = config["server"] + "states/game_rules"
    response = httpx.get(url)
    return ascifight.routers.states.RulesResponse.model_validate(response.json())


def get_timing() -> ascifight.routers.states.TimingResponse:
    url = config["server"] + "states/timing"
    response = httpx.get(url)
    return ascifight.routers.states.TimingResponse.model_validate(response.json())


def issue_order(order: str, actor_id: int, direction: Directions):
    httpx.post(
        url=f"{config['server']}orders/{order}/{actor_id}",
        params={"direction": direction.value},
        auth=(config["team"], str(config["password"])),
    )
    logger.info("Sent order", order=order, actor=actor_id, direction=direction)
