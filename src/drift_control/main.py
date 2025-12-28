import signal
import sys
import time
from pathlib import Path

import docker
import yaml
from rich.console import Console
from rich.panel import Panel

from .models import DesiredState
from .reconciler import Reconciler

console = Console()
CONFIG_FILE = Path("desired_state.yaml")
POLLING_INTERVAL = 5

RUNNING = True


def handle_signal(signum, frame):
    """Intercepts system signals for graceful shutdown."""
    global RUNNING

    console.print(f"\n[bold orange1]🛑 Signal {signum} received. Shutting down gracefully...[/bold orange1]")
    client = docker.from_env()

    try:
        container = client.containers.get("critical-service")
        print(f"🧹 Removing container: {container.name}...")
        container.stop()
        container.remove()
        print("✅ Cleanup complete.")
    except docker.errors.NotFound:
        print("⚠️ Container already gone.")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

    RUNNING = False
    print("System Offline.")
    sys.exit(0)


def load_setpoint() -> DesiredState:
    if not CONFIG_FILE.exists():
        console.print("[bold red]Fatal: desired_state.yaml not found.[/]")
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        raw_config = yaml.safe_load(f)

    return DesiredState.model_validate(raw_config)


def run_control_loop():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    console.print(
        Panel.fit(
            "[bold emerald]DriftControl Daemon[/bold emerald]\n"
            "Status: [green]ONLINE[/green]\n"
            "Strategy: [blue]Feedback Control Loop[/blue]",
            title="System Start",
        )
    )

    reconciler = Reconciler()

    while RUNNING:
        try:
            setpoint = load_setpoint()
            process_variable = reconciler.measure_actual_state(setpoint.app_name)
            error_signal = reconciler.calculate_deviation(setpoint, process_variable)

            if error_signal:
                reconciler.converge(setpoint, error_signal, process_variable)
            else:
                console.print(f"[dim green]✓ System Stable: {setpoint.app_name}[/dim green]", end="\r")

        except Exception as e:
            console.print(f"\n[bold red]Uncaught Loop Exception:[/bold red] {e}")

        for _ in range(POLLING_INTERVAL * 10):
            if not RUNNING:
                break
            time.sleep(0.1)

    console.print("[bold red]System Offline.[/bold red]")


if __name__ == "__main__":
    run_control_loop()
