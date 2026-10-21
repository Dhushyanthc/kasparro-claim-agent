import shutil
from datetime import date

import pytest

from claimagent.config import ROOT
from claimagent.data import parse_value, read_rows, verify_hashes
from claimagent.gold import load_gold


def test_quoted_comma_and_embedded_newline_are_exact(tmp_path):
    answer = "Line one, with a comma.\nLine two \"quoted\", still one cell. "
    path = tmp_path / "t.csv"
    path.write_bytes(('id,text\r\nA1,"' + answer.replace('"', '""') + '"\r\n').encode("utf-8"))
    assert read_rows(path)[0]["text"] == answer


def test_answers_split_counts(answers):
    splits = [a.split for a in answers.values()]
    assert len(answers) == 50 and splits.count("development") == 40 and splits.count("check") == 10


def test_every_gold_quote_equals_its_slice(answers):
    gold = load_gold()
    assert len(gold) == 376
    assert all(g.quote == answers[g.answer_id].ai_answer[g.start:g.end] for g in gold)
    assert all(g.claim_id == f"{g.answer_id}:{g.start}:{g.end}" for g in gold)


def test_boolean_parsing_is_strict():
    assert parse_value("boolean", "false") is False
    assert parse_value("boolean", "true") is True
    with pytest.raises(ValueError):
        parse_value("boolean", "False")


def test_number_parsing():
    assert parse_value("number", "5.0") == 5 and isinstance(parse_value("number", "5.0"), int)
    assert parse_value("number", "4.5") == 4.5


def test_facts_catalogue(facts):
    assert set(facts) == {"cleartrail", "stonewave", "cloudnote"}
    rows = [f for rows in facts.values() for f in rows]
    assert len(rows) == 132 and len({f.fact_id for f in rows}) == 132
    assert all(isinstance(f.valid_from, date) for f in rows)
    assert all(f.unit is None or f.unit for f in rows) and all(f.condition is None or f.condition for f in rows)


def test_hash_check_passes():
    assert set(verify_hashes()) == {"answers.csv", "brand_facts.csv", "development_gold.csv"}


def test_hash_check_fails_on_modified_copy(tmp_path):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    target = tmp_path / "data" / "brand_facts.csv"
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="brand_facts.csv"):
        verify_hashes(tmp_path)
