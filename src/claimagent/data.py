import csv
import hashlib
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from .config import DATA_DIR, ROOT

HASHED_FILES = ("answers.csv", "brand_facts.csv", "development_gold.csv")


@dataclass(frozen=True)
class Answer:
    answer_id: str
    split: str
    brand_id: str
    question: str
    ai_answer: str


@dataclass(frozen=True)
class Fact:
    fact_id: str
    brand_id: str
    model_id: str
    field: str
    value: bool | int | float | str
    unit: str | None
    condition: str | None
    valid_from: date
    valid_to: date


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_value(value_type: str, raw: str) -> bool | int | float | str:
    if value_type == "boolean":
        if raw not in ("true", "false"):
            raise ValueError(f"bad boolean {raw!r}")
        return raw == "true"
    if value_type == "number":
        number = float(raw)
        return int(number) if number.is_integer() else number
    if value_type == "string":
        return raw
    raise ValueError(f"bad value_type {value_type!r}")


@cache
def load_answers(path: Path = DATA_DIR / "answers.csv") -> dict[str, Answer]:
    answers = {r["answer_id"]: Answer(**r) for r in read_rows(path)}
    splits = [a.split for a in answers.values()]
    assert len(answers) == 50 and splits.count("development") == 40 and splits.count("check") == 10
    return answers


@cache
def load_facts(path: Path = DATA_DIR / "brand_facts.csv") -> dict[str, list[Fact]]:
    facts: dict[str, list[Fact]] = {}
    for r in read_rows(path):
        facts.setdefault(r["brand_id"], []).append(Fact(
            fact_id=r["fact_id"], brand_id=r["brand_id"], model_id=r["model_id"], field=r["field"],
            value=parse_value(r["value_type"], r["value"]),
            unit=r["unit"] or None, condition=r["condition"] or None,
            valid_from=date.fromisoformat(r["valid_from"]), valid_to=date.fromisoformat(r["valid_to"])))
    ids = [f.fact_id for rows in facts.values() for f in rows]
    assert len(ids) == 132 and len(set(ids)) == 132 and len(facts) == 3
    return facts


def verify_hashes(root: Path = ROOT) -> dict[str, str]:
    expected = {}
    for line in (root / "data" / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split()
        expected[Path(name).name] = digest
    actual = {n: hashlib.sha256((root / "data" / n).read_bytes()).hexdigest() for n in HASHED_FILES}
    bad = [n for n in HASHED_FILES if actual[n] != expected.get(n)]
    if bad:
        raise ValueError(f"hash mismatch: {', '.join(bad)}")
    return actual
