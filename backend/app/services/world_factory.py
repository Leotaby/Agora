"""
services/world_factory.py - WorldFactory

Builds the full world with all entity layers.
Instantiates all layers, wires connections, returns a ready World.


"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from app.models.world import World, GlobalMacroState
from app.models.country import build_all_countries
from app.models.political_actor import build_all_parties, build_all_governments
from app.models.institution import build_all_institutions
from app.models.geopolitical import build_all_sanctions, build_all_alliances
from app.models.nonstate_actor import build_all_nonstate_actors
from app.services.agent_factory import AgentFactory

console = Console()


class WorldFactory:
    """
    Builds the complete NEXUS world.

    Usage:
        factory = WorldFactory(seed=42)
        world = factory.build(n_households_per_major_country=200)
        print(world.summary())
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def build(
        self,
        n_households_per_major_country: int = 100,
        verbose: bool = True,
    ) -> World:
        """Build and wire all entity layers."""

        if verbose:
            console.print(Panel.fit(
                "[bold cyan]NEXUS = HumanTwin[/bold cyan]\n"
                "[dim]WorldFactory - initializing world[/dim]",
                border_style="cyan"
            ))

        world = World()

        # --- L1: Countries ---
        if verbose: console.print("[dim]L1[/dim] Populating nation-states...")
        world.countries = build_all_countries()
        if verbose: console.print(f"    {len(world.countries)} countries built")

        # --- L2: Political actors ---
        if verbose: console.print("[dim]L2[/dim] Installing governments and political parties...")
        parties = build_all_parties()
        governments = build_all_governments()
        # Store on political_actors dict (both parties and governments)
        world.political_actors = {**parties, **{f"GOV_{k}": v for k, v in governments.items()}}
        if verbose: console.print(f"    {len(parties)} parties, {len(governments)} governments")

        # --- L3: Institutions ---
        if verbose: console.print("[dim]L3[/dim] Establishing international institutions...")
        world.institutions = build_all_institutions()
        if verbose: console.print(f"    {len(world.institutions)} institutions")

        # --- Geopolitical structure ---
        if verbose: console.print("[dim]GEO[/dim] Applying sanctions regimes and alliances...")
        world.sanctions_regimes = build_all_sanctions()
        world.alliances = build_all_alliances()
        active = sum(1 for s in world.sanctions_regimes if s.active)
        if verbose: console.print(f"    {active} active sanctions regimes, {len(world.alliances)} alliances")

        # --- L5: Non-state actors ---
        if verbose: console.print("[dim]L5[/dim] Activating non-state actors...")
        world.nonstate_actors = build_all_nonstate_actors()
        if verbose: console.print(f"    {len(world.nonstate_actors)} non-state actors")

        # --- L7: Households ---
        if verbose: console.print("[dim]L7[/dim] Spawning household population...")
        agent_factory = AgentFactory(seed=self.seed)

        # Spawn households weighted by country population
        country_weights = {
            "DE": n_households_per_major_country,
            "FR": int(n_households_per_major_country * 0.8),
            "IT": int(n_households_per_major_country * 0.7),
            "US": int(n_households_per_major_country * 1.5),
            "CN": int(n_households_per_major_country * 0.6),  # smaller sample (data access)
            "IN": int(n_households_per_major_country * 0.5),
            "TR": int(n_households_per_major_country * 0.4),
            "AR": int(n_households_per_major_country * 0.3),
            "IR": int(n_households_per_major_country * 0.2),
            "RU": int(n_households_per_major_country * 0.3),
        }
        country_mix = []
        for country, n in country_weights.items():
            country_mix.extend([country] * n)

        world.households = agent_factory.build(
            n_households=len(country_mix),
            n_professional_retail=50,
            n_ordinary_retail=150,
            country_mix=country_mix,
        )
        if verbose:
            console.print(f"    {len(world.households)} agents spawned")

        if verbose:
            console.print(f"\n[green]World built.[/green]")
            self._print_world_summary(world)

        return world

    def _print_world_summary(self, world: World) -> None:
        from rich.table import Table
        from rich import box

        s = world.summary()
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("", style="dim", width=24)
        table.add_column("")
        for k, v in s.items():
            table.add_row(k.replace("_", " "), str(v))
        console.print(table)

        # Show sanctioned countries
        sanctioned = world.get_sanctioned_countries()
        console.print(f"\n[red]Sanctioned countries:[/red] {', '.join(sanctioned)}")

        swift_blocked = [c for c in sanctioned if not world.is_swift_connected(c)]
        if swift_blocked:
            console.print(f"[red]SWIFT-excluded:[/red] {', '.join(swift_blocked)}")
