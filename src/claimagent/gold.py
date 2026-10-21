from dataclasses import dataclass
from pathlib import Path

from .config import DATA_DIR
from .data import load_answers, read_rows


@dataclass(frozen=True)
class Gold:
    answer_id: str
    claim_id: str
    start: int
    end: int
    quote: str
    label: str
    evidence_fact_ids: tuple[str, ...]
    explanation: str
    tags: tuple[str, ...]


def load_gold(path: Path = DATA_DIR / "development_gold.csv") -> list[Gold]:
    answers = load_answers()
    gold = [Gold(r["answer_id"], r["claim_id"], int(r["start_char"]), int(r["end_char"]), r["quote"],
                 r["expected_label"], tuple(filter(None, r["evidence_fact_ids"].split("|"))),
                 r["explanation"], tuple(filter(None, r["difficulty_tags"].split("|"))))
            for r in read_rows(path)]
    assert len(gold) == 376
    for g in gold:
        assert g.quote == answers[g.answer_id].ai_answer[g.start:g.end], g.claim_id
    return gold
