import signal
import sys
import time

import docker
import yaml
from rich.console import Console
from rich.panel import Panel

from .models import DesiredState
from .reconciler import Reconciler
from .settings import get_settings

settings = get_settings()


class DriftControlDaemon:
    def __init__(self):
        self.console = Console()
        self.running = False
        self.reconciler = Reconciler()
        self._client = (
            docker.from_env(base_url=settings.DOCKER_BASE_URL) if settings.DOCKER_BASE_URL else docker.from_env()
        )

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def _load_setpoint(self) -> DesiredState:
        """Loads and validates the current desired state from disk."""
        if not settings.CONFIG_FILE.exists():
            self.console.print(f"[bold red]Fatal: {settings.CONFIG_FILE} not found.[/]")
            self.shutdown(None, None)
            sys.exit(1)

        with open(settings.CONFIG_FILE) as f:
            raw_config = yaml.safe_load(f)

        return DesiredState.model_validate(raw_config)

    def start(self):
        """Initializes the daemon and enters the main control loop."""
        self.running = True

        self.console.print(
            Panel.fit(
                "[bold emerald]DriftControl Daemon[/bold emerald]\n"
                f"Status: [green]ONLINE[/green]\n"
                f"Config: [blue]{settings.CONFIG_FILE}[/blue]\n"
                f"Strategy: [blue]Feedback Control Loop[/blue]",
                title="System Start",
            )
        )

        self.run_control_loop()

    def run_control_loop(self):
        """The main infinite loop observing and correcting drift."""
        while self.running:
            try:
                # 1. Measure & Plan
                setpoint = self._load_setpoint()
                process_variable = self.reconciler.measure_actual_state(setpoint.app_name)
                error_signal = self.reconciler.calculate_deviation(setpoint, process_variable)

                # 2. Act
                if error_signal:
                    self.reconciler.converge(setpoint, error_signal, process_variable)
                else:
                    self.console.print(f"[dim green]✓ System Stable: {setpoint.app_name}[/dim green]", end="\r")

            except Exception as e:
                self.console.print(f"\n[bold red]Uncaught Loop Exception:[/bold red] {e}")

            # 3. Wait (Interruptible sleep)
            self._interruptible_sleep(settings.POLLING_INTERVAL)

        self.console.print("[bold red]System Offline.[/bold red]")

    def _interruptible_sleep(self, duration: int):
        """Splits sleep into small chunks to allow immediate shutdown."""
        steps = int(duration / settings.CONTROL_INTERVAL)
        for _ in range(steps):
            if not self.running:
                break
            time.sleep(settings.CONTROL_INTERVAL)

    def shutdown(self, signum, frame):
        """Graceful shutdown sequence."""
        if not self.running:
            return

        self.console.print(f"\n[bold orange1]🛑 Signal {signum} received. Shutting down gracefully...[/bold orange1]")
        self.running = False

        try:
            container = self._client.containers.get("critical-service")
            self.console.print(f"🧹 Removing container: {container.name}...")
            container.stop()
            container.remove()
            self.console.print("✅ Cleanup complete.")
        except docker.errors.NotFound:
            self.console.print("⚠️ Container already gone.")
        except Exception as e:
            self.console.print(f"❌ Error during cleanup: {e}")


if __name__ == "__main__":
    app = DriftControlDaemon()
    app.start()
