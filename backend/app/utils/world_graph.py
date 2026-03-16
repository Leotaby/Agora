"""
Serialize the World model into a {nodes, edges} structure for D3 force graph.
"""
from __future__ import annotations

import math
from itertools import combinations

from app.models.world import World


THREAT_SIZE = {"minimal": 8, "low": 14, "medium": 22, "high": 35, "critical": 50}


def _flag(iso2: str) -> str:
    """Convert ISO2 country code to flag emoji."""
    if not iso2 or len(iso2) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def world_to_graph(world: World) -> dict:
    nodes = []
    edges = []
    country_ids = set(world.countries.keys())

    # --- Country nodes ---
    for iso2, country in world.countries.items():
        gdp = country.economy.gdp_usd_bn if hasattr(country, "economy") else 1000
        nodes.append({
            "id": iso2,
            "type": "country",
            "label": iso2,
            "size": max(4, math.log(max(1, gdp)) * 3),
            "data": {
                "name": country.name,
                "flag": _flag(iso2),
                "gdp_bn": round(gdp),
                "currency": getattr(country.economy, "currency_code", ""),
                "regime": getattr(country.politics, "regime_type", "").value
                    if hasattr(getattr(country, "politics", None), "regime_type") else "",
                "blocs": [b.value if hasattr(b, "value") else str(b)
                          for b in getattr(country, "blocs", [])],
                "sanctioned": getattr(country.politics, "sanctions_target", False)
                    if hasattr(country, "politics") else False,
            },
        })

    # --- Institution nodes ---
    for inst_id, inst in world.institutions.items():
        nodes.append({
            "id": inst_id,
            "type": "institution",
            "label": inst_id,
            "size": inst.enforcement_power * 40 + 5,
            "data": {
                "name": inst.name,
                "inst_type": inst.institution_type.value,
                "hq": inst.headquarters_country,
                "enforcement": round(inst.enforcement_power, 2),
                "narrative": round(inst.narrative_power, 2),
            },
        })

    # --- Non-state actor nodes ---
    for actor in world.nonstate_actors:
        nodes.append({
            "id": actor.actor_id,
            "type": "nonstate_actor",
            "label": actor.actor_id[:12],
            "size": THREAT_SIZE.get(actor.threat_level.value, 14),
            "data": {
                "name": actor.name,
                "actor_type": actor.actor_type.value,
                "hq": actor.headquarter_country or "stateless",
                "threat": actor.threat_level.value,
                "cyber": round(actor.cyber_capability, 2),
                "sponsors": actor.state_sponsors,
            },
        })

    node_ids = {n["id"] for n in nodes}

    # --- Sanctions edges (directed) ---
    for regime in world.sanctions_regimes:
        if not regime.active:
            continue
        for sender in regime.sender_countries:
            for target in regime.target_countries:
                if sender in node_ids and target in node_ids:
                    edges.append({
                        "source": sender,
                        "target": target,
                        "type": "sanctions",
                        "directed": True,
                        "label": regime.name[:30],
                    })

    # --- Alliance edges (undirected, between existing country nodes) ---
    for alliance in world.alliances:
        present = [m for m in alliance.members if m in country_ids]
        for a, b in combinations(present, 2):
            edges.append({
                "source": a,
                "target": b,
                "type": "alliance",
                "directed": False,
                "label": alliance.name,
            })

    # --- Institution membership edges ---
    for inst_id, inst in world.institutions.items():
        for member in inst.member_countries:
            if isinstance(member, str) and member in country_ids:
                edges.append({
                    "source": inst_id,
                    "target": member,
                    "type": "institution_member",
                    "directed": False,
                })

    # --- Trade edges (undirected, deduplicated) ---
    seen_trade = set()
    for iso2, country in world.countries.items():
        for partner in getattr(country, "trade_partners", []):
            if partner in country_ids:
                pair = tuple(sorted([iso2, partner]))
                if pair not in seen_trade:
                    seen_trade.add(pair)
                    edges.append({
                        "source": pair[0],
                        "target": pair[1],
                        "type": "trade",
                        "directed": False,
                    })

    # --- State sponsor edges (directed) ---
    for actor in world.nonstate_actors:
        for sponsor in actor.state_sponsors:
            if sponsor in country_ids:
                edges.append({
                    "source": sponsor,
                    "target": actor.actor_id,
                    "type": "state_sponsor",
                    "directed": True,
                })

    return {"nodes": nodes, "edges": edges}
