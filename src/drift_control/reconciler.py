import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container
from rich.console import Console

from .models import DesiredState

console = Console()


class Reconciler:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            console.print(f"[bold red]CRITICAL: Could not connect to Docker Daemon.[/] {e}")
            exit(1)

    def measure_actual_state(self, app_name: str) -> Container | None:
        try:
            return self.client.containers.get(app_name)
        except NotFound:
            return None

    def calculate_deviation(self, desired: DesiredState, actual: Container | None) -> str | None:
        if not actual:
            return "Container missing (State: Null)"

        if actual.status != "running":
            return f"Status deviation (Actual: {actual.status} != Desired: running)"

        actual_tags = actual.image.tags
        if desired.image not in actual_tags:
            return f"Image mismatch (Actual: {actual_tags} != Desired: {desired.image})"

        ports = actual.attrs["NetworkSettings"]["Ports"]
        port_key = f"{desired.container_port}/tcp"

        if port_key not in ports or not ports[port_key]:
            return f"Port definition missing for {desired.container_port}"

        mapped_host_port = int(ports[port_key][0]["HostPort"])

        is_primary = mapped_host_port == desired.host_port
        is_fallback = desired.fallback_host_port and mapped_host_port == desired.fallback_host_port

        if not (is_primary or is_fallback):
            return (
                f"Port Drift (Actual: {mapped_host_port} != Desired: {desired.host_port} or "
                "{desired.fallback_host_port})"
            )

        return None

    def converge(self, desired: DesiredState, deviation_reason: str, actual: Container | None):
        console.print(f"[bold yellow]⚠️  DRIFT DETECTED:[/bold yellow] {deviation_reason}")
        console.print("[blue]⚙️  Actuator: Initiating convergence sequence...[/blue]")

        try:
            if actual:
                console.print(f"   [dim]Stopping and removing container '{actual.name}'...[/dim]")
                actual.stop()
                actual.remove()

            self._try_start_container(desired, use_fallback=False)

        except APIError as e:
            console.print(f"[bold red]❌ Actuator Failure:[/bold red] {e}")

    def _try_start_container(self, desired: DesiredState, use_fallback: bool):
        """
        Helper to attempt container start.
        If Primary port fails with 'Bind' error, it cleans up and recurses to Fallback.
        """
        target_port = desired.fallback_host_port if use_fallback else desired.host_port

        if not target_port:
            console.print("[bold red]❌ No fallback port defined. Giving up.[/bold red]")
            return

        try:
            self.client.images.pull(desired.image)
        except APIError:
            console.print("   [dim red]Warning: Could not pull image. Trying local cache...[/dim red]")
        except ImageNotFound:
            console.print(f"   [bold red]Error: Image {desired.image} not found locally or remotely.[/bold red]")
            return

        console.print(f"   [dim]Provisioning new instance on Port {target_port}...[/dim]")

        try:
            self.client.containers.run(
                desired.image, name=desired.app_name, ports={f"{desired.container_port}/tcp": target_port}, detach=True
            )
            console.print(f"[bold green]✅ SYSTEM HEALED: State converged to Port {target_port}[/bold green]")

        except APIError as e:
            err_str = str(e).lower()

            port_busy_signatures = [
                "address already in use",
                "port is already allocated",
                "bind for",
                "failed to bind host port",
                "programming external connectivity",
            ]

            is_port_error = any(sig in err_str for sig in port_busy_signatures)

            if is_port_error:
                if not use_fallback and desired.fallback_host_port:
                    console.print(
                        f"[bold orange1]⚠️  Port {desired.host_port} busy. Attempting fallback to "
                        "{desired.fallback_host_port}...[/bold orange1]"
                    )

                    try:
                        failed_container = self.client.containers.get(desired.app_name)
                        failed_container.remove(force=True)
                    except NotFound:
                        pass  # The failed_container wasn't created, safe to proceed

                    self._try_start_container(desired, use_fallback=True)
                    return
                else:
                    console.print(f"[bold red]❌ Port {target_port} blocked and no viable fallbacks.[/bold red]")
                    raise e
            else:
                raise e
