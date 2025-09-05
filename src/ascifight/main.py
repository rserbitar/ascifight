import logging
import logging.config
import asyncio
from contextlib import asynccontextmanager
import os

import uvicorn

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import structlog

import ascifight.config as config
import ascifight.routers.orders as orders
import ascifight.routers.states as states
import ascifight.routers.other as other
import ascifight.routers.router_utils as router_utils

import ascifight.util as util
import ascifight.game_loop as game_loop

try:
    os.mkdir(config.config["server"]["log_dir"])
except FileExistsError:
    pass

logging.config.dictConfig(util.log_config_dict)


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        util.time_stamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

root_logger = logging.getLogger()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):  # pyright: ignore [reportUnusedParameter]

    logger.info("Starting server.")
    asyncio.create_task(game_loop.routine())
    yield


app = FastAPI(
    lifespan=lifespan,
    openapi_tags=router_utils.tags_metadata,
    title="A Social, Community Increasing - Fight",
    description=util.api_description,
    version="0.2.0",
    contact={
        "name": "Ralf Kelzenberg",
        "url": "http://vodafone.com",
        "email": "Ralf.Kelzenberg@vodafone.com",
    },
)

app.include_router(orders.router)
app.include_router(states.router)
app.include_router(other.router)
app.mount(
    "/logs", StaticFiles(directory=config.config["server"]["log_dir"]), name="logs"
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
