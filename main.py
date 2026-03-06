"""Taipy CLI entrypoint.

Run with:
  taipy run main.py
"""

# Re-export GUI-bound names so Taipy can resolve root-page bindings when
# launched through `taipy run main.py`.
from app import menu_lov, on_menu_action, run_app  # noqa: F401


if __name__ == "__main__":
    run_app()
