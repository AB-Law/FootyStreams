"""Initial schema: one table per stored model, append-only triggers on the ledger and event log.

Revision ID: 0001
Revises:
Create Date: 2026-10-07 20:52:00.098377
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

APPEND_ONLY = ("ledger_entries", "match_events")

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upgrade_part_1() -> None:
    """Part 1 of the upgrade steps."""
    op.create_table(
        "competitions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "media_personalities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("owner_kind", sa.String(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("created_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "nations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("is_home", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "proposals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "referees",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("reputation", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "relationships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("a_kind", sa.String(), nullable=True),
        sa.Column("a_id", sa.String(), nullable=True),
        sa.Column("b_kind", sa.String(), nullable=True),
        sa.Column("b_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("relationships", schema=None) as batch_op:
        batch_op.create_index("ix_relationships_a_kind_a_id", ["a_kind", "a_id"], unique=False)
        batch_op.create_index("ix_relationships_b_kind_b_id", ["b_kind", "b_id"], unique=False)
    op.create_table(
        "state_modifiers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("owner_kind", sa.String(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("start_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=True),
        sa.Column("origin", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("state_modifiers", schema=None) as batch_op:
        batch_op.create_index(
            "ix_state_modifiers_owner_kind_owner_id", ["owner_kind", "owner_id"], unique=False
        )


def _upgrade_part_2() -> None:
    """Part 2 of the upgrade steps."""
    op.create_table(
        "world_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=True),
        sa.Column("origin", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("world_events", schema=None) as batch_op:
        batch_op.create_index("ix_world_events_date", ["date"], unique=False)
    op.create_table(
        "world_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("delta_hash", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "world_meta",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("nation_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("climate", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["nation_id"],
            ["nations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cities", schema=None) as batch_op:
        batch_op.create_index("ix_cities_nation_id", ["nation_id"], unique=False)
    op.create_table(
        "clubs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("short_code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("reputation", sa.Integer(), nullable=True),
        sa.Column("balance", sa.Integer(), nullable=True),
        sa.Column("nation_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["nation_id"],
            ["nations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code", name="uq_clubs_short_code"),
    )
    with op.batch_alter_table("clubs", schema=None) as batch_op:
        batch_op.create_index("ix_clubs_nation_id", ["nation_id"], unique=False)
    op.create_table(
        "seasons",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("competition_id", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.create_index("ix_seasons_competition_id", ["competition_id"], unique=False)


def _upgrade_part_3() -> None:
    """Part 3 of the upgrade steps."""
    op.create_table(
        "fixtures",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("season_id", sa.String(), nullable=True),
        sa.Column("competition_id", sa.String(), nullable=True),
        sa.Column("matchday", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("home_club_id", sa.String(), nullable=True),
        sa.Column("away_club_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("match_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["away_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["home_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.create_index("ix_fixtures_away_club_id", ["away_club_id"], unique=False)
        batch_op.create_index("ix_fixtures_competition_id", ["competition_id"], unique=False)
        batch_op.create_index("ix_fixtures_home_club_id", ["home_club_id"], unique=False)
        batch_op.create_index("ix_fixtures_season_id", ["season_id"], unique=False)
        batch_op.create_index(
            "ix_fixtures_season_id_matchday", ["season_id", "matchday"], unique=False
        )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("ref_type", sa.String(), nullable=True),
        sa.Column("ref_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ledger_entries", schema=None) as batch_op:
        batch_op.create_index("ix_ledger_entries_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_ledger_entries_club_id_date", ["club_id", "date"], unique=False)
    op.create_table(
        "managers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("reputation", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("managers", schema=None) as batch_op:
        batch_op.create_index("ix_managers_club_id", ["club_id"], unique=False)
    op.create_table(
        "players",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("primary_position", sa.String(), nullable=True),
        sa.Column("ability_current", sa.Integer(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("squad_status", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("injured", sa.Boolean(), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=True),
        sa.Column("market_value", sa.Integer(), nullable=True),
        sa.Column("wage_weekly", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.create_index("ix_players_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_players_squad_status", ["squad_status"], unique=False)
        batch_op.create_index("ix_players_status", ["status"], unique=False)
    op.create_table(
        "staff",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("reputation", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.create_index("ix_staff_club_id", ["club_id"], unique=False)


def _upgrade_part_4() -> None:
    """Part 4 of the upgrade steps."""
    op.create_table(
        "standings_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("season_id", sa.String(), nullable=True),
        sa.Column("after_matchday", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("standings_snapshots", schema=None) as batch_op:
        batch_op.create_index("ix_standings_snapshots_season_id", ["season_id"], unique=False)
    op.create_table(
        "transfer_windows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("season_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("opens_on", sa.Date(), nullable=True),
        sa.Column("closes_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("transfer_windows", schema=None) as batch_op:
        batch_op.create_index("ix_transfer_windows_season_id", ["season_id"], unique=False)
    op.create_table(
        "matches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("fixture_id", sa.String(), nullable=True),
        sa.Column("season_id", sa.String(), nullable=True),
        sa.Column("matchday", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("home_club_id", sa.String(), nullable=True),
        sa.Column("away_club_id", sa.String(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("config_hash", sa.String(), nullable=True),
        sa.Column("sim_version", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.Column("log_digest", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["away_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
        ),
        sa.ForeignKeyConstraint(
            ["home_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.create_index("ix_matches_away_club_id", ["away_club_id"], unique=False)
        batch_op.create_index("ix_matches_fixture_id", ["fixture_id"], unique=False)
        batch_op.create_index("ix_matches_home_club_id", ["home_club_id"], unique=False)
        batch_op.create_index("ix_matches_season_id", ["season_id"], unique=False)
    op.create_table(
        "scout_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("created_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scout_reports", schema=None) as batch_op:
        batch_op.create_index("ix_scout_reports_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_scout_reports_player_id", ["player_id"], unique=False)
    op.create_table(
        "squad_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("squad_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "club_id", "squad_number", name="uq_squad_entries_club_id_squad_number"
        ),
    )
    with op.batch_alter_table("squad_entries", schema=None) as batch_op:
        batch_op.create_index("ix_squad_entries_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_squad_entries_player_id", ["player_id"], unique=False)


def _upgrade_part_5() -> None:
    """Part 5 of the upgrade steps."""
    op.create_table(
        "transfer_bids",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("window_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("from_club_id", sa.String(), nullable=True),
        sa.Column("to_club_id", sa.String(), nullable=True),
        sa.Column("fee", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["from_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["transfer_windows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("transfer_bids", schema=None) as batch_op:
        batch_op.create_index("ix_transfer_bids_from_club_id", ["from_club_id"], unique=False)
        batch_op.create_index("ix_transfer_bids_player_id", ["player_id"], unique=False)
        batch_op.create_index("ix_transfer_bids_to_club_id", ["to_club_id"], unique=False)
        batch_op.create_index("ix_transfer_bids_window_id", ["window_id"], unique=False)
    op.create_table(
        "transfer_listings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("window_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("asking_price", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["transfer_windows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("transfer_listings", schema=None) as batch_op:
        batch_op.create_index("ix_transfer_listings_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_transfer_listings_player_id", ["player_id"], unique=False)
        batch_op.create_index("ix_transfer_listings_window_id", ["window_id"], unique=False)
    op.create_table(
        "transfers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("from_club_id", sa.String(), nullable=True),
        sa.Column("to_club_id", sa.String(), nullable=True),
        sa.Column("fee", sa.Integer(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["from_club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.ForeignKeyConstraint(
            ["to_club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("transfers", schema=None) as batch_op:
        batch_op.create_index("ix_transfers_from_club_id", ["from_club_id"], unique=False)
        batch_op.create_index("ix_transfers_player_id", ["player_id"], unique=False)
        batch_op.create_index("ix_transfers_to_club_id", ["to_club_id"], unique=False)
    op.create_table(
        "contract_offers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("bid_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("club_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bid_id"],
            ["transfer_bids.id"],
        ),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("contract_offers", schema=None) as batch_op:
        batch_op.create_index("ix_contract_offers_bid_id", ["bid_id"], unique=False)
        batch_op.create_index("ix_contract_offers_club_id", ["club_id"], unique=False)
        batch_op.create_index("ix_contract_offers_player_id", ["player_id"], unique=False)
    op.create_table(
        "match_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("match_id", sa.String(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("tick", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("match_events", schema=None) as batch_op:
        batch_op.create_index("ix_match_events_match_id", ["match_id"], unique=False)
        batch_op.create_index("ix_match_events_match_id_type", ["match_id", "type"], unique=False)


def _upgrade_part_6() -> None:
    """Part 6 of the upgrade steps."""
    op.create_table(
        "match_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("match_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("match_summaries", schema=None) as batch_op:
        batch_op.create_index("ix_match_summaries_match_id", ["match_id"], unique=False)
    for table in APPEND_ONLY:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{action.lower()} BEFORE {action} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )


def _downgrade_part_1() -> None:
    """Part 1 of the downgrade steps."""
    for table in APPEND_ONLY:
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER trg_{table}_no_{action}")
    with op.batch_alter_table("match_summaries", schema=None) as batch_op:
        batch_op.drop_index("ix_match_summaries_match_id")
    op.drop_table("match_summaries")
    with op.batch_alter_table("match_events", schema=None) as batch_op:
        batch_op.drop_index("ix_match_events_match_id_type")
        batch_op.drop_index("ix_match_events_match_id")
    op.drop_table("match_events")
    with op.batch_alter_table("contract_offers", schema=None) as batch_op:
        batch_op.drop_index("ix_contract_offers_player_id")
        batch_op.drop_index("ix_contract_offers_club_id")
        batch_op.drop_index("ix_contract_offers_bid_id")
    op.drop_table("contract_offers")
    with op.batch_alter_table("transfers", schema=None) as batch_op:
        batch_op.drop_index("ix_transfers_to_club_id")
        batch_op.drop_index("ix_transfers_player_id")
        batch_op.drop_index("ix_transfers_from_club_id")
    op.drop_table("transfers")
    with op.batch_alter_table("transfer_listings", schema=None) as batch_op:
        batch_op.drop_index("ix_transfer_listings_window_id")
        batch_op.drop_index("ix_transfer_listings_player_id")
        batch_op.drop_index("ix_transfer_listings_club_id")


def _downgrade_part_2() -> None:
    """Part 2 of the downgrade steps."""
    op.drop_table("transfer_listings")
    with op.batch_alter_table("transfer_bids", schema=None) as batch_op:
        batch_op.drop_index("ix_transfer_bids_window_id")
        batch_op.drop_index("ix_transfer_bids_to_club_id")
        batch_op.drop_index("ix_transfer_bids_player_id")
        batch_op.drop_index("ix_transfer_bids_from_club_id")
    op.drop_table("transfer_bids")
    with op.batch_alter_table("squad_entries", schema=None) as batch_op:
        batch_op.drop_index("ix_squad_entries_player_id")
        batch_op.drop_index("ix_squad_entries_club_id")
    op.drop_table("squad_entries")
    with op.batch_alter_table("scout_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_scout_reports_player_id")
        batch_op.drop_index("ix_scout_reports_club_id")
    op.drop_table("scout_reports")
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_index("ix_matches_season_id")
        batch_op.drop_index("ix_matches_home_club_id")
        batch_op.drop_index("ix_matches_fixture_id")
        batch_op.drop_index("ix_matches_away_club_id")
    op.drop_table("matches")
    with op.batch_alter_table("transfer_windows", schema=None) as batch_op:
        batch_op.drop_index("ix_transfer_windows_season_id")


def _downgrade_part_3() -> None:
    """Part 3 of the downgrade steps."""
    op.drop_table("transfer_windows")
    with op.batch_alter_table("standings_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_standings_snapshots_season_id")
    op.drop_table("standings_snapshots")
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_index("ix_staff_club_id")
    op.drop_table("staff")
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_index("ix_players_status")
        batch_op.drop_index("ix_players_squad_status")
        batch_op.drop_index("ix_players_club_id")
    op.drop_table("players")
    with op.batch_alter_table("managers", schema=None) as batch_op:
        batch_op.drop_index("ix_managers_club_id")
    op.drop_table("managers")
    with op.batch_alter_table("ledger_entries", schema=None) as batch_op:
        batch_op.drop_index("ix_ledger_entries_club_id_date")
        batch_op.drop_index("ix_ledger_entries_club_id")


def _downgrade_part_4() -> None:
    """Part 4 of the downgrade steps."""
    op.drop_table("ledger_entries")
    with op.batch_alter_table("fixtures", schema=None) as batch_op:
        batch_op.drop_index("ix_fixtures_season_id_matchday")
        batch_op.drop_index("ix_fixtures_season_id")
        batch_op.drop_index("ix_fixtures_home_club_id")
        batch_op.drop_index("ix_fixtures_competition_id")
        batch_op.drop_index("ix_fixtures_away_club_id")
    op.drop_table("fixtures")
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_index("ix_seasons_competition_id")
    op.drop_table("seasons")
    with op.batch_alter_table("clubs", schema=None) as batch_op:
        batch_op.drop_index("ix_clubs_nation_id")
    op.drop_table("clubs")
    with op.batch_alter_table("cities", schema=None) as batch_op:
        batch_op.drop_index("ix_cities_nation_id")
    op.drop_table("cities")
    op.drop_table("world_meta")


def _downgrade_part_5() -> None:
    """Part 5 of the downgrade steps."""
    op.drop_table("world_log")
    with op.batch_alter_table("world_events", schema=None) as batch_op:
        batch_op.drop_index("ix_world_events_date")
    op.drop_table("world_events")
    with op.batch_alter_table("state_modifiers", schema=None) as batch_op:
        batch_op.drop_index("ix_state_modifiers_owner_kind_owner_id")
    op.drop_table("state_modifiers")
    with op.batch_alter_table("relationships", schema=None) as batch_op:
        batch_op.drop_index("ix_relationships_b_kind_b_id")
        batch_op.drop_index("ix_relationships_a_kind_a_id")
    op.drop_table("relationships")
    op.drop_table("referees")
    op.drop_table("proposals")
    op.drop_table("nations")


def _downgrade_part_6() -> None:
    """Part 6 of the downgrade steps."""
    op.drop_table("memories")
    op.drop_table("media_personalities")
    op.drop_table("competitions")


def upgrade() -> None:
    """Create the tables, indexes and append-only triggers."""
    _upgrade_part_1()
    _upgrade_part_2()
    _upgrade_part_3()
    _upgrade_part_4()
    _upgrade_part_5()
    _upgrade_part_6()


def downgrade() -> None:
    """Drop the triggers, indexes and tables."""
    _downgrade_part_1()
    _downgrade_part_2()
    _downgrade_part_3()
    _downgrade_part_4()
    _downgrade_part_5()
    _downgrade_part_6()
