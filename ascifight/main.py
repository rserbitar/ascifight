import logging, logging.config, logging.handlers
import asyncio
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import structlog


import ascifight.config as config
import ascifight.routers.orders as orders
import ascifight.routers.states as states
import ascifight.routers.other as other
import ascifight.routers.computations as computations

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


tags_metadata = [
    {
        "name": "orders",
        "description": "Operations to give orders to your actors.",
    },
    {
        "name": "states",
        "description": "Operations to get state information about the game.",
    },
    {
        "name": "logistics",
        "description": "Operations to provide quality of life support.",
    },
    {
        "name": "computations",
        "description": "Computational functions that help to create 'AI' scripts.",
    },
    {
        "name": "web-page",
        "description": "Web-pages to display various information.",
    },
]


app = FastAPI(
    openapi_tags=tags_metadata,
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
app.include_router(computations.router)
app.mount(
    "/logs", StaticFiles(directory=config.config["server"]["log_dir"]), name="logs"
)


@app.on_event("startup")
async def startup():
    logger.info("Starting server.")
    asyncio.create_task(game_loop.routine())
