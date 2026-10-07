"""People checks: ability, names, nationality mix, referees and the broadcast crew."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import sqrt

from footystreams.domain.media import MediaRole
from footystreams.domain.ratings import compute_current_ability
from footystreams.domain.textfold import plain
from footystreams.domain.world import World
from footystreams.verify.violation import Violation
from footystreams.verify.world_refs import Findings
from footystreams.verify.world_targets import WorldChecks, WorldTargets

DISPOSITIONS = (
    "ambition", "loyalty", "professionalism", "volatility", "sportsmanship",
    "ego", "sociability", "humor", "media_openness", "resilience",
)  # fmt: skip


def check_abilities(world: World, checks: WorldChecks) -> list[Violation]:
    """W09 CA <= PA; W10 the cached CA equals the ability recomputed from attributes."""
    findings = Findings("W09")
    cached = Findings("W10")
    for player in world.players:
        findings.expect(
            player.id,
            f"potential {player.ability_potential} is below current {player.ability_current}",
            holds=player.ability_potential >= player.ability_current,
        )
        recomputed = compute_current_ability(player, checks.roles)
        cached.expect(
            player.id,
            f"cached ability {player.ability_current} differs from recomputed {recomputed}",
            holds=recomputed == player.ability_current,
        )
    return [*findings.problems, *cached.problems]


def check_names(world: World, checks: WorldChecks, targets: WorldTargets) -> list[Violation]:
    """C01 unique known_as and bounded surname repeats (kin excepted); C02 denylist."""
    people = [*world.players, *world.managers, *world.staff, *world.referees, *world.media]
    findings = Findings("C01")
    for name, count in Counter(person.known_as for person in people).items():
        findings.expect(name, "known_as is used by more than one person", holds=count == 1)
    kin = {end.id for row in world.relationships if row.kind == "family" for end in (row.a, row.b)}
    surnames = Counter(plain(p.last_name) for p in people if p.id not in kin)
    for surname, count in surnames.items():
        findings.expect(
            surname,
            f"surname is shared by {count} people",
            holds=count <= targets.max_surname_repeats,
        )
    denied = Findings("C02")
    for person in people:
        hit = (
            plain(person.last_name) in checks.denylist or plain(person.known_as) in checks.denylist
        )
        denied.expect(person.id, "name is on the real-world denylist", holds=not hit)
    return [*findings.problems, *denied.problems]


def check_nationality_mix(world: World, targets: WorldTargets) -> list[Violation]:
    """C03: each senior squad has several nationalities and no nation dominates."""
    findings = Findings("C03")
    for club in world.clubs:
        seniors = [
            p
            for p in world.players
            if p.contract and p.contract.club_id == club.id and not p.is_youth
        ]
        mix = Counter(p.nationality for p in seniors)
        findings.expect(
            club.id,
            f"only {len(mix)} nationalities",
            holds=len(mix) >= targets.min_nationalities,
        )
        top = max(mix.values(), default=0) / max(len(seniors), 1)
        findings.expect(
            club.id, f"one nation makes up {top:.0%}", holds=top <= targets.max_nation_share
        )
    return findings.problems


def check_referees(world: World, targets: WorldTargets) -> list[Violation]:
    """C04: the pool has a strict, a lenient and a card-happy referee; mean home bias is mild."""
    findings = Findings("C04")
    refs = world.referees
    findings.expect(
        "referees",
        "no strict referee",
        holds=any(r.strictness >= targets.strict_referee for r in refs),
    )
    findings.expect(
        "referees",
        "no lenient referee",
        holds=any(r.strictness <= targets.lenient_referee for r in refs),
    )
    findings.expect(
        "referees",
        "no card-happy referee",
        holds=any(r.card_tendency >= targets.card_happy_referee for r in refs),
    )
    mean = sum(r.home_bias for r in refs) / max(len(refs), 1)
    low, high = targets.home_bias_mean_band
    findings.expect(
        "referees", f"mean home bias {mean:.2f} is outside {low}-{high}", holds=low <= mean <= high
    )
    return findings.problems


def check_crew(world: World, targets: WorldTargets) -> list[Violation]:
    """C05: every media role is filled, voices are unique, personalities are distinct."""
    findings = Findings("C05")
    roles = {m.role for m in world.media}
    for role in MediaRole:
        findings.expect(role.value, "no one fills the media role", holds=role in roles)
    voices = Counter(binding.voice_id for m in world.media for binding in m.voice.bindings.values())
    for voice_id, count in voices.items():
        findings.expect(voice_id, "voice id is used twice", holds=count == 1)
    for left, right in combinations(world.media, 2):
        distance = sqrt(
            sum(
                (getattr(left.personality, f) - getattr(right.personality, f)) ** 2
                for f in DISPOSITIONS
            )
        )
        findings.expect(
            f"{left.id}/{right.id}",
            f"personalities are only {distance:.0f} apart",
            holds=distance >= targets.min_crew_distance,
        )
    return findings.problems


def check_managers(world: World, checks: WorldChecks) -> list[Violation]:
    """C06: manager formations exist in the catalogue and the preferred one is his best."""
    findings = Findings("C06")
    known = set(checks.formations.formations)
    for manager in world.managers:
        used = {
            manager.preferred_formation,
            *manager.fallback_formations,
            *manager.formation_proficiency,
        }
        findings.expect(manager.id, "uses a formation outside the catalogue", holds=used <= known)
        best = max(manager.formation_proficiency.values(), default=0)
        preferred = manager.formation_proficiency.get(manager.preferred_formation, 0)
        findings.expect(
            manager.id, "is not best at his preferred formation", holds=preferred == best
        )
    return findings.problems


def check_prospect_flags(world: World) -> list[Violation]:
    """C07: a club's academy prospects are exactly its youth players."""
    youth: dict[str, set[str]] = {str(club.id): set() for club in world.clubs}
    for player in world.players:
        if player.is_youth and player.contract is not None:
            youth.setdefault(str(player.contract.club_id), set()).add(str(player.id))
    findings = Findings("C07")
    for club in world.clubs:
        findings.expect(
            club.id,
            "academy prospects are not exactly the club's youth players",
            holds={str(i) for i in club.academy.prospect_ids} == youth[str(club.id)],
        )
    return findings.problems
