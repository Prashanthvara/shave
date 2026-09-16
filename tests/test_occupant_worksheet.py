"""Which rows need an operating business, and how research survives re-runs."""

import csv

import pandas as pd
import pytest

from shave import occupant_worksheet as ow
from shave import occupants


def _frames():
    rows = []
    # Worcester: 3 comstock, 1 modeled. Lowell: 1 comstock, 1 modeled. One dropped row.
    spec = [
        ("W1", 348, "comstock", 9000.0, True), ("W2", 348, "comstock", 8000.0, True),
        ("W3", 348, "comstock", 100.0, True), ("W4", 348, "modeled", 7000.0, True),
        ("L1", 160, "comstock", 50.0, True), ("L2", 160, "modeled", 40.0, True),
        ("X9", 348, "comstock", 99_999.0, False),
    ]
    for loc_id, town_id, source, usd, keep in spec:
        rows.append({"loc_id": loc_id, "source": source, "annual_savings_usd": usd, "keep": keep})
    scored = pd.DataFrame(rows)
    parcels = pd.DataFrame([{
        "loc_id": loc_id, "town_id": town_id, "site_addr": f"{loc_id} MAIN ST",
        "owner": f"{loc_id} REALTY TRUST", "use_desc": "Warehouse", "sqft": 10_000.0,
    } for loc_id, town_id, *_ in spec])
    return scored, parcels


def test_selection_is_the_top_n_plus_every_towns_list_heads_minus_resolved():
    scored, parcels = _frames()

    rows = ow.select_rows(scored, parcels, existing={"W2"}, top_n=2)

    ids = list(rows["loc_id"])
    # top 2 kept by dollars: W1, W2 (W2 already resolved); heads: W1, W4, L1, L2
    assert set(ids) == {"W1", "W4", "L1", "L2"}
    assert "X9" not in ids, "a dropped row is never on the list"
    assert ids == sorted(ids, key=lambda i: -dict(zip(scored.loc_id, scored.annual_savings_usd))[i])
    lowell_head = rows.set_index("loc_id").loc["L1"]
    assert (lowell_head["town"], lowell_head["list"], lowell_head["rank"]) == ("Lowell", "comstock", 1)


def test_selection_survives_a_scored_frame_that_already_carries_town_id():
    """The real pipeline frame has town_id, so the merge must not make
    town_id_x/town_id_y and fail the rank groupby."""
    scored, parcels = _frames()
    scored = scored.assign(
        town_id=[348, 348, 348, 348, 160, 160, 348][: len(scored)]
    )

    rows = ow.select_rows(scored, parcels, existing={"W2"}, top_n=2)

    assert set(rows["loc_id"]) == {"W1", "W4", "L1", "L2"}


def test_rewriting_the_worksheet_keeps_every_research_cell(tmp_path):
    scored, parcels = _frames()
    path = tmp_path / "candidates.csv"
    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        table = list(csv.DictReader(fh))
    for row in table:
        if row["loc_id"] == "L1":
            row.update(candidate_occupant="Acme Mills", candidate_source="https://acme.example/lowell",
                       evidence="Contact page lists L1 MAIN ST.", status="verified", reviewer="PJ")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ow.FIELDS)
        writer.writeheader()
        writer.writerows(table)

    ow.write_worksheet(ow.select_rows(scored, parcels, existing=set(), top_n=2), path)

    with path.open(newline="", encoding="utf-8") as fh:
        again = {r["loc_id"]: r for r in csv.DictReader(fh)}
    assert again["L1"]["candidate_occupant"] == "Acme Mills"
    assert again["L1"]["status"] == "verified" and again["L1"]["reviewer"] == "PJ"
    assert again["W4"]["status"] == "pending"


def test_a_new_row_starts_pending_with_empty_research():
    scored, parcels = _frames()
    rows = ow.select_rows(scored, parcels, existing=set(), top_n=1)
    assert set(rows["status"]) == {"pending"}
    assert set(rows["candidate_occupant"]) == {""}


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ow.FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f, "") for f in ow.FIELDS})


def _occupants(tmp_path):
    path = tmp_path / "occupants.csv"
    path.write_text("loc_id,occupant,occupant_source,verified_on,note\n"
                    "OLD,Old Co,https://old.example/,2026-09-11,\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clean_occupant_cache():
    occupants.load.cache_clear()
    yield
    occupants.load.cache_clear()


def test_only_verified_initialled_sourced_rows_are_promoted(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [
        {"loc_id": "A", "candidate_occupant": "Acme Mills", "candidate_source": "https://acme.example/",
         "evidence": "Site lists the address.", "status": "verified", "reviewer": "PJ"},
        {"loc_id": "B", "candidate_occupant": "Beta Co", "candidate_source": "https://beta.example/",
         "status": "pending"},
        {"loc_id": "C", "candidate_occupant": "Gamma", "candidate_source": "https://g.example/",
         "status": "rejected", "reviewer": "PJ"},
        {"loc_id": "OLD", "candidate_occupant": "Old Co", "candidate_source": "https://old.example/",
         "status": "verified", "reviewer": "PJ"},
    ])
    occ = _occupants(tmp_path)

    added = ow.promote(cands, occ, today="2026-09-20")

    assert added == 1
    table = occupants.load(occ)
    assert set(table) == {"OLD", "A"}
    assert table["A"].occupant == "Acme Mills"
    assert table["A"].verified_on == "2026-09-20"
    assert "PJ" in table["A"].note and "Site lists the address." in table["A"].note


def test_a_verified_row_without_a_reviewer_is_refused(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [{"loc_id": "A", "candidate_occupant": "Acme", "candidate_source": "https://a.example/",
                    "status": "verified"}])
    occ = _occupants(tmp_path)
    before = occ.read_text(encoding="utf-8")

    with pytest.raises(occupants.OccupantError, match="reviewer"):
        ow.promote(cands, occ, today="2026-09-20")
    assert occ.read_text(encoding="utf-8") == before


def test_a_verified_row_without_a_web_source_is_refused(tmp_path):
    cands = tmp_path / "c.csv"
    _write(cands, [{"loc_id": "A", "candidate_occupant": "Acme", "candidate_source": "Google",
                    "status": "verified", "reviewer": "PJ"}])
    with pytest.raises(occupants.OccupantError, match="source"):
        ow.promote(cands, _occupants(tmp_path), today="2026-09-20")


def test_a_capitalised_status_counts_and_a_mistyped_one_is_refused(tmp_path):
    """Reviewers edit this CSV by hand. 'Verified' must promote, and 'verfied'
    must stop with an error rather than silently never reaching the table."""
    occ = _occupants(tmp_path)
    good = tmp_path / "good.csv"
    _write(good, [{"loc_id": "A", "candidate_occupant": "Acme", "candidate_source": "https://a.example/",
                   "status": " Verified ", "reviewer": "PJ"}])
    assert ow.promote(good, occ, today="2026-09-20") == 1

    bad = tmp_path / "bad.csv"
    _write(bad, [{"loc_id": "B", "candidate_occupant": "Beta", "candidate_source": "https://b.example/",
                  "status": "verfied", "reviewer": "PJ"}])
    before = occ.read_text(encoding="utf-8")
    with pytest.raises(occupants.OccupantError, match="verfied"):
        ow.promote(bad, occ, today="2026-09-20")
    assert occ.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# update_research: the only writer of the agent's three columns.
# ---------------------------------------------------------------------------

def _worksheet(tmp_path, rows):
    import csv

    from shave import occupant_worksheet as ow

    path = tmp_path / "candidates.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ow.FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in ow.FIELDS})
    return path


FINDING = {
    "candidate_occupant": "Burlington",
    "candidate_source": "https://www.burlington.com/stores/ma/fall-river/752",
    "evidence": "Burlington's own store page gives that address.",
}


def test_update_research_fills_a_pending_row(tmp_path):
    from shave import occupant_worksheet as ow

    path = _worksheet(tmp_path, [{"loc_id": "A", "status": "pending"}])
    assert ow.update_research(path, {"A": FINDING}) == 1

    row = ow._read(path)["A"]
    assert row["candidate_occupant"] == "Burlington"
    assert row["status"] == "pending", "the agent must never set a status"
    assert row["reviewer"] == ""


def test_update_research_never_overwrites_a_reviewed_row(tmp_path):
    """A person's judgment outranks a re-run. Verified and rejected rows, and
    any row someone has initialled, are left exactly as they are."""
    from shave import occupant_worksheet as ow

    path = _worksheet(
        tmp_path,
        [
            {"loc_id": "V", "status": "verified", "reviewer": "pj",
             "candidate_occupant": "Checked Co"},
            {"loc_id": "R", "status": "rejected", "reviewer": "pj",
             "candidate_occupant": "Wrong Co"},
            {"loc_id": "P", "status": "pending", "reviewer": "pj",
             "candidate_occupant": "Looking Into It"},
        ],
    )
    assert ow.update_research(path, {k: FINDING for k in ("V", "R", "P")}) == 0

    rows = ow._read(path)
    assert rows["V"]["candidate_occupant"] == "Checked Co"
    assert rows["R"]["candidate_occupant"] == "Wrong Co"
    assert rows["P"]["candidate_occupant"] == "Looking Into It"


def test_update_research_leaves_rows_it_was_given_no_finding_for(tmp_path):
    from shave import occupant_worksheet as ow

    path = _worksheet(
        tmp_path,
        [{"loc_id": "A", "status": "pending"},
         {"loc_id": "B", "status": "pending", "evidence": "already looked"}],
    )
    ow.update_research(path, {"A": FINDING})

    rows = ow._read(path)
    assert rows["A"]["candidate_occupant"] == "Burlington"
    assert rows["B"]["evidence"] == "already looked"


def test_update_research_keeps_the_column_order(tmp_path):
    from shave import occupant_worksheet as ow

    path = _worksheet(tmp_path, [{"loc_id": "A", "status": "pending"}])
    ow.update_research(path, {"A": FINDING})
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(ow.FIELDS)


def test_the_agent_may_not_write_a_status_or_a_reviewer():
    """A structural guarantee, not a convention: the fields the agent is
    allowed to write cannot include the ones that gate promotion."""
    from shave import occupant_worksheet as ow

    assert set(ow.AGENT_FIELDS).isdisjoint({"status", "reviewer", "reviewer_note"})
