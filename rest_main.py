"""Taipy REST API entrypoint.

Run with:
  taipy run rest_main.py
"""

import taipy as tp
from dotenv import load_dotenv
from taipy import Rest

# Import project config so DataNodes/Tasks/Scenarios are registered.
import core_config  # noqa: F401
from services.auth0_rest import maybe_enable_auth0_rest_auth

load_dotenv()


def run_rest():
    rest_service = Rest()
    maybe_enable_auth0_rest_auth(rest_service._app)
    tp.run(rest_service)


if __name__ == "__main__":
    run_rest()
