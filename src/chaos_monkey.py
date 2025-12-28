import random
import time

import docker
from docker.errors import APIError, NotFound
from rich.console import Console
from rich.panel import Panel

from drift_control.settings import get_settings

console = Console()

settings = get_settings()


class ChaosMonkey:
    """
    The Agent of Chaos.
    Randomly injects faults into the system to test the Control Loop's resilience.
    """

    def __init__(self, target_name: str = "critical-service"):
        self.target_name = target_name
        self.client = docker.from_env()
        self.rogue_image = settings.ROGUE_IMAGE
        self.rogue_port = settings.ROGUE_PORT

    def _get_container(self):
        try:
            return self.client.containers.get(self.target_name)
        except NotFound:
            return None

    def attack_terminate(self):
        """Action: Hard Kill (SIGKILL)"""
        container = self._get_container()
        if container and container.status == "running":
            console.print(f"[bold red]🔥 ATTACK: Sending SIGKILL to {self.target_name}...[/bold red]")
            container.kill()
        else:
            console.print("[dim]⚠️ Target already down, skipping attack...[/dim]")

    def attack_stop(self):
        """Action: Graceful Stop (SIGTERM)"""
        container = self._get_container()
        if container and container.status == "running":
            console.print(f"[bold orange1]🛑 ATTACK: Stopping {self.target_name}...[/bold orange1]")
            container.stop()
        else:
            console.print("[dim]⚠️ Target already down, skipping attack...[/dim]")

    def attack_rogue_deployment(self):
        """Action: Configuration Drift (Wrong Image)"""
        console.print("[bold magenta]🎭 ATTACK: Deploying Rogue Container (Image Drift)...[/bold magenta]")

        container = self._get_container()
        if container:
            try:
                container.remove(force=True)
            except APIError:
                pass

        try:
            self.client.images.pull(self.rogue_image)
            self.client.containers.run(
                self.rogue_image,
                name=self.target_name,
                ports={"80/tcp": self.rogue_port},
                detach=True,
            )
            console.print(
                f"   [magenta]↳ Deployed '{self.rogue_image}' (Apache) masquerading as critical-service[/magenta]"
            )
        except APIError as e:
            console.print(f"[red]Failed to deploy rogue:[/red] {e}")

    def unleash(self):
        """Main Loop"""
        console.print(
            Panel.fit(
                "[bold red]👹 Chaos Monkey Active[/bold red]\n"
                "Target: [white]critical-service[/white]\n"
                "Interval: [white]Random (5-15s)[/white]",
                title="System Test",
            )
        )

        actions = [
            self.attack_terminate,
            self.attack_stop,
            self.attack_rogue_deployment,
        ]

        while True:
            wait_time = random.randint(8, 15)
            console.print(f"\n[dim]⏳ Lurking for {wait_time} seconds...[/dim]")
            time.sleep(wait_time)

            attack = random.choice(actions)
            attack()


if __name__ == "__main__":
    monkey = ChaosMonkey()
    try:
        monkey.unleash()
    except KeyboardInterrupt:
        console.print("\n[green]Chaos Monkey retained.[/green]")
