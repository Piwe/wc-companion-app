from types import SimpleNamespace

from app.progression import build_knockout_path, compute_progression, humanize_stage

TEAM = 1
OPP = 2


def match(**kw):
    base = dict(
        id=kw.get("id", 100),
        stage="GROUP_STAGE",
        status="FINISHED",
        winner=None,
        home_team_id=TEAM,
        away_team_id=OPP,
        home_score=None,
        away_score=None,
        utc_date=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def standing(position, played, points=0):
    return SimpleNamespace(position=position, played=played, points=points)


# --------------------------------------------------------------- knockout progression


def test_qualified_playing_next_round():
    matches = [
        match(id=1, stage="GROUP_STAGE", winner="HOME_TEAM", home_score=2, away_score=0),
        match(id=2, stage="ROUND_OF_16", status="SCHEDULED", winner=None),
    ]
    result = compute_progression(TEAM, matches, standing(1, 3))
    assert result["qualified"] is True
    assert result["eliminated"] is False
    assert "Round of 16" in result["status"]


def test_eliminated_in_knockout():
    matches = [
        match(id=2, stage="ROUND_OF_16", winner="AWAY_TEAM", home_score=0, away_score=1),
    ]
    result = compute_progression(TEAM, matches, standing(1, 3))
    assert result["eliminated"] is True
    assert result["qualified"] is True
    assert "Eliminated" in result["status"]
    assert "Round of 16" in result["status"]


def test_champions():
    matches = [
        match(id=9, stage="FINAL", winner="HOME_TEAM", home_score=3, away_score=1),
    ]
    result = compute_progression(TEAM, matches, standing(1, 3))
    assert result["eliminated"] is False
    assert "Champions" in result["status"]


def test_won_but_awaiting_next_fixture():
    matches = [
        match(id=2, stage="QUARTER_FINALS", winner="HOME_TEAM", home_score=1, away_score=0),
    ]
    result = compute_progression(TEAM, matches, standing(1, 3))
    assert result["qualified"] is True
    assert result["eliminated"] is False
    assert "Advanced past" in result["status"]


# --------------------------------------------------------------- group-stage heuristics


def test_group_in_progress_leading():
    result = compute_progression(TEAM, [], standing(1, 2))
    assert result["qualified"] is False
    assert result["eliminated"] is False
    assert "qualifying position" in result["status"]


def test_group_complete_third_in_contention():
    result = compute_progression(TEAM, [], standing(3, 3))
    assert result["eliminated"] is False
    assert "best third" in result["status"].lower()


def test_group_complete_fourth_eliminated():
    result = compute_progression(TEAM, [], standing(4, 3))
    assert result["eliminated"] is True
    assert "Eliminated" in result["status"]


def test_group_complete_top_two_advances():
    result = compute_progression(TEAM, [], standing(2, 3))
    assert result["qualified"] is True
    assert "Advanced from group" in result["status"]


# --------------------------------------------------------------- knockout path


def test_knockout_path_ordering_and_results():
    matches = [
        match(id=5, stage="QUARTER_FINALS", status="SCHEDULED", winner=None),
        match(id=3, stage="GROUP_STAGE", winner="HOME_TEAM"),  # excluded from path
        match(
            id=4,
            stage="ROUND_OF_16",
            winner="HOME_TEAM",
            home_score=2,
            away_score=1,
            utc_date=None,
        ),
    ]
    names = {OPP: "Rivals FC"}
    path = build_knockout_path(TEAM, matches, names)
    assert [p["stage"] for p in path] == ["ROUND_OF_16", "QUARTER_FINALS"]
    assert path[0]["result"] == "won"
    assert path[0]["score"] == "2-1"
    assert path[0]["opponent_name"] == "Rivals FC"
    assert path[1]["result"] == "upcoming"


def test_humanize_stage():
    assert humanize_stage("ROUND_OF_16") == "Round of 16"
    assert humanize_stage("LAST_16") == "Round of 16"
    assert humanize_stage("QUARTER_FINALS") == "Quarter-finals"
    assert humanize_stage(None) == "Unknown"
