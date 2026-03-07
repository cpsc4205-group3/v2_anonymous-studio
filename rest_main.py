"""Taipy REST API entrypoint.

Run with:
  taipy run rest_main.py
"""

from dotenv import load_dotenv

# Load .env before any project module so env-var-gated config (core_config,
# auth0_rest) reads the correct values at import time.
load_dotenv()

import taipy as tp  # noqa: E402
from taipy import Rest  # noqa: E402

# Import project config so DataNodes/Tasks/Scenarios are registered.
import core_config  # noqa: F401, E402
from services.auth0_rest import maybe_enable_auth0_rest_auth  # noqa: E402


def run_rest():
    rest_service = Rest()
    maybe_enable_auth0_rest_auth(rest_service._app)
    tp.run(rest_service)


if __name__ == "__main__":
    run_rest()
