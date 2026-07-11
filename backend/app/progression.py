"""Pure functions that derive a team's tournament progression.

These functions read only plain attributes off match/standing objects, so they can be
unit-tested with lightweight stand-ins (see tests/test_progression.py) without a database.

Design note: rather than reimplementing FIFA's "best third-placed" qualification algorithm,
authoritative advancement is read straight from the knockout matches feed — a team that has a
scheduled or won knockout match has advanced; a team that lost its latest knockout match is
out. Group-stage labels are lightweight heuristics used only while the group stage is live.
"""

GROUP_STAGE = "GROUP_STAGE"

# Football-Data has used both LAST_* and ROUND_OF_* codings across competitions; support both.
STAGE_ORDER = [
    GROUP_STAGE,
    "ROUND_OF_32",
    "LAST_32",
    "ROUND_OF_16",
    "LAST_16",
    "QUARTER_FINALS",
    "SEMI_FINALS",
    "THIRD_PLACE",
    "FINAL",
]

STAGE_DISPLAY = {
    GROUP_STAGE: "Group Stage",
    "ROUND_OF_32": "Round of 32",
    "LAST_32": "Round of 32",
    "ROUND_OF_16": "Round of 16",
    "LAST_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-finals",
    "SEMI_FINALS": "Semi-finals",
    "THIRD_PLACE": "Third-place play-off",
    "FINAL": "Final",
}

FINISHED = "FINISHED"
GROUP_STAGE_GAMES = 3  # each team plays 3 group games in a group of 4


def humanize_stage(stage: str | None) -> str:
    if not stage:
        return "Unknown"
    return STAGE_DISPLAY.get(stage, stage.replace("_", " ").title())


def _stage_rank(stage: str | None) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except (ValueError, TypeError):
        return -1


def _is_knockout(match) -> bool:
    return getattr(match, "stage", GROUP_STAGE) != GROUP_STAGE


def _team_won(match, team_id: int) -> bool | None:
    """True if team won, False if lost, None if draw/undecided."""
    winner = getattr(match, "winner", None)
    if winner == "DRAW":
        return None
    if winner == "HOME_TEAM":
        return match.home_team_id == team_id
    if winner == "AWAY_TEAM":
        return match.away_team_id == team_id
    return None


def _score_str(match, team_id: int) -> str | None:
    if match.home_score is None or match.away_score is None:
        return None
    if match.home_team_id == team_id:
        return f"{match.home_score}-{match.away_score}"
    return f"{match.away_score}-{match.home_score}"


def build_knockout_path(team_id: int, matches, team_names: dict[int, str]) -> list[dict]:
    """Ordered list of the team's knockout matches with per-match result."""
    ko = [m for m in matches if _is_knockout(m)]
    ko.sort(key=lambda m: _stage_rank(getattr(m, "stage", None)))
    path = []
    for m in ko:
        opponent_id = m.away_team_id if m.home_team_id == team_id else m.home_team_id
        if m.status == FINISHED:
            won = _team_won(m, team_id)
            result = "won" if won is True else "lost" if won is False else "draw"
        else:
            result = "upcoming"
        path.append(
            {
                "stage": getattr(m, "stage", None),
                "match_id": m.id,
                "opponent_name": team_names.get(opponent_id) if opponent_id else None,
                "utc_date": getattr(m, "utc_date", None),
                "result": result,
                "score": _score_str(m, team_id),
            }
        )
    return path


def compute_progression(team_id: int, matches, standing) -> dict:
    """Return {"status", "qualified", "eliminated"} for a team."""
    ko = [m for m in matches if _is_knockout(m)]

    if ko:
        return _knockout_progression(team_id, ko)
    return _group_progression(standing)


def _knockout_progression(team_id: int, ko_matches) -> dict:
    ko_sorted = sorted(ko_matches, key=lambda m: _stage_rank(getattr(m, "stage", None)))
    furthest = ko_sorted[-1]
    furthest_stage = getattr(furthest, "stage", None)

    finished = [m for m in ko_sorted if m.status == FINISHED]

    # Did they lose their latest finished knockout match?
    if finished:
        latest = finished[-1]
        won = _team_won(latest, team_id)
        if won is False:
            stage = getattr(latest, "stage", None)
            return {
                "status": f"Eliminated — {humanize_stage(stage)}",
                "qualified": True,  # they did qualify from the group; just knocked out later
                "eliminated": True,
            }
        if won is True and getattr(latest, "stage", None) == "FINAL":
            return {"status": "Champions 🏆", "qualified": True, "eliminated": False}

    # Still alive: reached (or awaiting) the furthest stage.
    if furthest.status == FINISHED:
        # Won their latest match but no next fixture scheduled yet — awaiting draw.
        return {
            "status": f"Advanced past {humanize_stage(furthest_stage)}",
            "qualified": True,
            "eliminated": False,
        }
    return {
        "status": f"Qualified — playing {humanize_stage(furthest_stage)}",
        "qualified": True,
        "eliminated": False,
    }


def _group_progression(standing) -> dict:
    if standing is None:
        return {"status": "Awaiting fixtures", "qualified": False, "eliminated": False}

    position = standing.position
    played = standing.played
    remaining = max(0, GROUP_STAGE_GAMES - played)

    if remaining == 0:
        # Group complete: top 2 advance directly; 3rd may advance as a best third-placed team.
        if position <= 2:
            return {"status": "Advanced from group", "qualified": True, "eliminated": False}
        if position == 3:
            return {
                "status": "In contention (best third-placed)",
                "qualified": False,
                "eliminated": False,
            }
        return {"status": "Eliminated — Group Stage", "qualified": False, "eliminated": True}

    # Group stage still in progress — lightweight heuristic from current position.
    if position <= 2:
        return {"status": "In qualifying position", "qualified": False, "eliminated": False}
    if position == 3:
        return {"status": "In contention", "qualified": False, "eliminated": False}
    return {"status": "Must win to advance", "qualified": False, "eliminated": False}
