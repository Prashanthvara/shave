"""The crosswalk is the domain judgment of the project, so it is tested hard.

Two classes of test live here. The first pins the committed `crosswalk.csv`:
row count, coverage split, and the invariants that make a row believable — a
`comstock` row naming a type NREL actually models, a `modeled` row naming a type
NREL explicitly does not. The second drives the validator through every branch
with a throwaway CSV, because the failure mode that matters is a mistyped row
producing a plausible score with no error at all.

`crosswalk.load` is `lru_cache(maxsize=1)`, and `archetype_for`/`assert_covers`
call it with no argument. A temp-file test therefore poisons the cache for every
test that follows it, so the autouse fixture below clears it either side of
every test in the module.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from shave import crosswalk
from shave.crosswalk import (
    COMSTOCK_TYPES,
    EXCLUDE,
    MEDIUM_OFFICE_MAX_SQFT,
    MODELED_TYPES,
    SMALL_OFFICE_MAX_SQFT,
    CrosswalkError,
)

HEADER = ["use_code", "use_desc", "archetype", "source", "icp_sector", "confidence",
          "note", "multi_meter"]

EXPECTED_ROWS = 95
EXPECTED_COVERAGE = {
    "total": 95,
    "comstock": 50,
    "modeled": 16,
    "excluded": 29,
    "collapse_points": 2,
}


@pytest.fixture(autouse=True)
def _clean_crosswalk_cache():
    crosswalk.load.cache_clear()
    yield
    crosswalk.load.cache_clear()


def write_crosswalk(tmp_path: Path, rows: list[dict[str, str]], name: str = "cw.csv") -> Path:
    """A throwaway crosswalk CSV. Rows are dicts over HEADER; missing keys blank."""
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in HEADER})
    return path


def good_row(**overrides: str) -> dict[str, str]:
    base = {
        "use_code": "3160",
        "use_desc": "Other Storage, Warehouse and Distribution",
        "archetype": "warehouse",
        "source": "comstock",
        "icp_sector": "11",
        "confidence": "HIGH",
        "note": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# the committed file
# ---------------------------------------------------------------------------


def test_load_returns_the_expected_number_of_rows():
    rows = crosswalk.load()
    assert len(rows) == EXPECTED_ROWS


def test_coverage_summary_matches_the_published_split():
    assert crosswalk.coverage_summary() == EXPECTED_COVERAGE


def test_coverage_summary_partitions_the_file():
    summary = crosswalk.coverage_summary()
    # comstock + modeled + excluded is the whole file: there is no fourth state.
    assert summary["comstock"] + summary["modeled"] + summary["excluded"] == summary["total"]


def test_every_comstock_archetype_is_a_comstock_type():
    offenders = {
        code: row.archetype
        for code, row in crosswalk.load().items()
        if row.source == "comstock" and row.archetype not in COMSTOCK_TYPES
    }
    assert offenders == {}


def test_every_modeled_archetype_is_a_known_modeled_type():
    offenders = {
        code: row.archetype
        for code, row in crosswalk.load().items()
        if row.source == "modeled" and row.archetype not in MODELED_TYPES
    }
    assert offenders == {}


def test_no_modeled_archetype_duplicates_something_comstock_measures():
    offenders = {
        code: row.archetype
        for code, row in crosswalk.load().items()
        if row.source == "modeled" and row.archetype in COMSTOCK_TYPES
    }
    assert offenders == {}


def test_comstock_and_modeled_type_sets_are_disjoint():
    # The two type sets must stay disjoint. `_validate_row` checks ComStock
    # membership first, so a `source=modeled` row naming a measured type gets
    # the specific reason rather than a generic "unknown type". If the sets ever
    # overlap, an archetype could be both measured and modelled and the
    # validator would stop being able to tell the caller which it is. This test
    # fails first, at the definition, rather than leaving that to a data row.
    assert COMSTOCK_TYPES.isdisjoint(MODELED_TYPES)


def test_excluded_rows_carry_no_source():
    offenders = {
        code: row.source for code, row in crosswalk.load().items() if row.excluded and row.source
    }
    assert offenders == {}


def test_non_excluded_rows_have_an_archetype_and_a_source():
    for code, row in crosswalk.load().items():
        if row.excluded:
            continue
        assert row.archetype, f"{code} has a blank archetype"
        assert row.source in ("comstock", "modeled"), f"{code} has source {row.source!r}"


def test_every_row_has_a_valid_confidence():
    assert {row.confidence for row in crosswalk.load().values()} <= {"HIGH", "MED", "LOW"}


def test_no_duplicate_use_codes_in_the_committed_file():
    # `load` raises on a duplicate, so a silent merge would show up as a row
    # count below the number of physical lines in the file.
    with crosswalk.CROSSWALK_PATH.open(newline="", encoding="utf-8") as fh:
        codes = [row["use_code"].strip() for row in csv.DictReader(fh)]
    assert len(codes) == len(set(codes)) == EXPECTED_ROWS


def test_the_two_collapse_points_are_the_ones_the_docstring_names():
    collapse = {code for code, row in crosswalk.load().items() if row.is_collapse_point}
    assert collapse == {"4000", "4010"}


def test_use_codes_are_strings_not_integers():
    # Worcester carries `942C` and `995`. Anything that coerces the column to
    # an integer loses both, and 995 would silently become 995 != "995".
    codes = set(crosswalk.load())
    assert "942C" in codes
    assert "995" in codes


# ---------------------------------------------------------------------------
# resolve_office_band
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sqft, expected",
    [
        (0, "small_office"),
        (1, "small_office"),
        (SMALL_OFFICE_MAX_SQFT - 1, "small_office"),
        (SMALL_OFFICE_MAX_SQFT, "small_office"),          # boundary is inclusive
        (SMALL_OFFICE_MAX_SQFT + 1, "medium_office"),
        (MEDIUM_OFFICE_MAX_SQFT - 1, "medium_office"),
        (MEDIUM_OFFICE_MAX_SQFT, "medium_office"),        # boundary is inclusive
        (MEDIUM_OFFICE_MAX_SQFT + 1, "large_office"),
        (5_000_000, "large_office"),
    ],
)
def test_resolve_office_band(sqft, expected):
    assert crosswalk.resolve_office_band(sqft) == expected


def test_office_band_edges_are_where_the_constants_say():
    assert SMALL_OFFICE_MAX_SQFT == 20_000
    assert MEDIUM_OFFICE_MAX_SQFT == 100_000


# ---------------------------------------------------------------------------
# archetype_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sqft, expected",
    [
        (2_500, "small_office"),
        (SMALL_OFFICE_MAX_SQFT, "small_office"),
        (SMALL_OFFICE_MAX_SQFT + 1, "medium_office"),
        (60_000, "medium_office"),
        (MEDIUM_OFFICE_MAX_SQFT, "medium_office"),
        (MEDIUM_OFFICE_MAX_SQFT + 1, "large_office"),
        (450_000, "large_office"),
    ],
)
def test_archetype_for_3400_resolves_the_office_band(sqft, expected):
    row = crosswalk.archetype_for("3400", sqft)
    assert row is not None
    assert row.archetype == expected
    # Everything else about the row survives the substitution.
    assert row.use_code == "3400"
    assert row.source == "comstock"
    assert row.use_desc == "General Office Buildings"


def test_archetype_for_does_not_mutate_the_cached_office_row():
    crosswalk.archetype_for("3400", 450_000)
    assert crosswalk.load()["3400"].archetype == "office"


def test_archetype_for_office_family_without_sqft_raises():
    with pytest.raises(CrosswalkError, match="sqft is required"):
        crosswalk.archetype_for("3400")


def test_archetype_for_an_excluded_code_returns_none():
    assert crosswalk.load()["3360"].excluded  # Parking Garages
    assert crosswalk.archetype_for("3360", 50_000) is None


def test_archetype_for_an_unknown_code_raises():
    with pytest.raises(CrosswalkError, match="9999"):
        crosswalk.archetype_for("9999", 10_000)


def test_archetype_for_tolerates_surrounding_whitespace():
    assert crosswalk.archetype_for(" 3160 ", 10_000).archetype == "warehouse"


def test_archetype_for_a_non_office_code_ignores_sqft():
    small = crosswalk.archetype_for("3160", 1_000)
    large = crosswalk.archetype_for("3160", 900_000)
    assert small.archetype == large.archetype == "warehouse"


# ---------------------------------------------------------------------------
# assert_covers
# ---------------------------------------------------------------------------


def test_assert_covers_passes_on_the_full_committed_set():
    crosswalk.assert_covers(set(crosswalk.load()))


def test_assert_covers_passes_on_a_subset():
    crosswalk.assert_covers({"3160", "4000", "995"})


def test_assert_covers_ignores_blank_codes():
    crosswalk.assert_covers({"3160", "", "   "})


def test_assert_covers_names_the_missing_codes():
    with pytest.raises(CrosswalkError) as excinfo:
        crosswalk.assert_covers({"3160", "1010", "0000"})
    message = str(excinfo.value)
    assert "1010" in message
    assert "0000" in message
    assert "2 use code(s)" in message
    # The codes that *are* covered are not named as problems.
    assert "3160" not in message


def test_assert_covers_truncates_a_very_long_missing_list():
    missing = {f"X{n:04d}" for n in range(40)}
    with pytest.raises(CrosswalkError) as excinfo:
        crosswalk.assert_covers(missing)
    assert "40 use code(s)" in str(excinfo.value)
    assert str(excinfo.value).rstrip().endswith("...")


# ---------------------------------------------------------------------------
# the validator, branch by branch
# ---------------------------------------------------------------------------


def test_missing_file_raises(tmp_path):
    with pytest.raises(CrosswalkError, match="not found"):
        crosswalk.load(tmp_path / "nope.csv")


def test_empty_file_raises(tmp_path):
    path = write_crosswalk(tmp_path, [])
    with pytest.raises(CrosswalkError, match="no rows"):
        crosswalk.load(path)


def test_a_well_formed_temp_file_loads(tmp_path):
    path = write_crosswalk(
        tmp_path,
        [
            good_row(),
            good_row(use_code="4000", archetype="industrial_manufacturing", source="modeled", confidence="LOW"),
            good_row(use_code="3360", archetype=EXCLUDE, source="", confidence="HIGH"),
        ],
    )
    rows = crosswalk.load(path)
    assert set(rows) == {"3160", "4000", "3360"}
    assert rows["3360"].excluded


def test_blank_use_code_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(use_code="")])
    with pytest.raises(CrosswalkError, match="blank use_code"):
        crosswalk.load(path)


def test_duplicate_use_code_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(), good_row(use_desc="again")])
    with pytest.raises(CrosswalkError, match="duplicate use_code '3160'"):
        crosswalk.load(path)


def test_bad_confidence_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(confidence="PROBABLY")])
    with pytest.raises(CrosswalkError, match="confidence must be HIGH/MED/LOW"):
        crosswalk.load(path)


def test_comstock_source_with_a_non_comstock_archetype_raises(tmp_path):
    # `ice_rink` is real, but NREL names ice rinks as explicitly not modelled.
    path = write_crosswalk(tmp_path, [good_row(archetype="ice_rink", source="comstock")])
    with pytest.raises(CrosswalkError, match="is not a ComStock type"):
        crosswalk.load(path)


def test_modeled_source_with_a_comstock_archetype_raises(tmp_path):
    # `warehouse` is measured by ComStock, so it must never be sourced as
    # modelled. The ComStock membership check runs first, so the error names the
    # real reason rather than falling through to "unknown modeled type".
    path = write_crosswalk(tmp_path, [good_row(archetype="warehouse", source="modeled")])
    with pytest.raises(CrosswalkError, match="measured by ComStock"):
        crosswalk.load(path)


def test_blank_archetype_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(archetype="")])
    with pytest.raises(CrosswalkError, match="archetype is blank"):
        crosswalk.load(path)


def test_excluded_row_with_a_source_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(archetype=EXCLUDE, source="comstock")])
    with pytest.raises(CrosswalkError, match="excluded rows must have an empty source"):
        crosswalk.load(path)


def test_unknown_source_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(source="vibes")])
    with pytest.raises(CrosswalkError, match="source must be 'comstock' or 'modeled'"):
        crosswalk.load(path)


def test_an_unrecognised_modeled_archetype_raises(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(archetype="bowling_alley", source="modeled")])
    with pytest.raises(CrosswalkError, match="not a known modeled type"):
        crosswalk.load(path)


def test_confidence_is_upper_cased_and_defaults_to_low(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(confidence="med")])
    assert crosswalk.load(path)["3160"].confidence == "MED"


def test_the_error_message_names_the_file_and_the_line(tmp_path):
    path = write_crosswalk(tmp_path, [good_row(), good_row(use_code="3161", confidence="X")])
    with pytest.raises(CrosswalkError) as excinfo:
        crosswalk.load(path)
    message = str(excinfo.value)
    assert path.name in message
    assert ":3" in message          # header is line 1, first data row line 2
    assert "3161" in message


def test_strip_mall_rows_are_flagged_multi_meter():
    """A strip mall is many service accounts. Demand bills per account, so a
    parcel-level estimate for one is an aggregate nobody is billed for."""
    rows = crosswalk.load()
    strip = [r for r in rows.values() if r.archetype == "strip_mall"]
    assert strip, "the crosswalk must still map something to strip_mall"
    assert all(r.multi_meter for r in strip)


def test_single_occupant_archetypes_are_not_flagged():
    rows = crosswalk.load()
    assert not rows["3050"].multi_meter, "a private hospital is one account"


def test_multi_meter_rejects_an_unrecognised_value(tmp_path):
    """A typo must not read as False. These columns only ever remove
    confidence, so a misparse fails open and over-grades the row."""
    path = write_crosswalk(tmp_path, [good_row(multi_meter="yes")])
    with pytest.raises(CrosswalkError, match="multi_meter must be 0 or 1"):
        crosswalk.load(path)


def test_multi_meter_column_absent_defaults_to_false(tmp_path):
    """A crosswalk written before the column existed still loads."""
    path = tmp_path / "old.csv"
    legacy = [h for h in HEADER if h != "multi_meter"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=legacy)
        writer.writeheader()
        writer.writerow({k: good_row().get(k, "") for k in legacy})
    assert crosswalk.load(path)["3160"].multi_meter is False


def test_every_shipped_crosswalk_row_has_exactly_the_header_fields():
    """Regression: use code 4100 carried an unquoted comma in its note, so it
    parsed as eight fields against a seven-field header and silently lost the
    tail of the note. Harmless while `note` was last; the moment a column was
    appended after it, the overflow landed in that new column instead."""
    with crosswalk.CROSSWALK_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        for lineno, row in enumerate(reader, start=2):
            assert None not in row, (
                f"line {lineno} (use_code {row['use_code']}) has more fields than the "
                f"header — an unquoted comma. Overflow: {row[None]!r}"
            )
            assert set(row) == fields, f"line {lineno} is missing fields"
