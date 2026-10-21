import json

import pytest

from claimagent import harness
from claimagent.data import Answer
from claimagent.gold import Gold

SENTS = [f"Claim number {k} is stated here." for k in range(14)]
TEXT = " ".join(SENTS)
LABELS = ["supported", "contradicted", "unknown"]


def span(k):
    start = sum(len(s) + 1 for s in SENTS[:k])
    return start, start + len(SENTS[k])


def gold(k, label=None, aid="S1", tags=("price",)):
    start, end = span(k)
    return Gold(aid, f"{aid}:{start}:{end}", start, end, SENTS[k], label or LABELS[k % 3], (), "", tags)


def pred(k, label=None, aid="S1"):
    start, end = span(k)
    return {"claim_id": f"{aid}:{start}:{end}", "start_char": start, "end_char": end, "quote": SENTS[k],
            "label": label or LABELS[k % 3], "fact_ids": [], "reason": "r.", "parts": []}


def ok(claims, aid="S1", latency=1):
    return {"answer_id": aid, "status": "ok", "error_type": None, "claims": claims, "latency_ms": latency}


def err(aid="S1", kind="timeout"):
    return {"answer_id": aid, "status": "error", "error_type": kind, "claims": [], "latency_ms": 5}


def answers(*ids):
    return {i: Answer(i, "development", "cleartrail", "q", TEXT) for i in ids}


def run_score(outcomes, golds, split="development"):
    ids = [o["answer_id"] for o in outcomes]
    return harness.score(split, ids, outcomes, answers(*ids), golds)


GOLD10 = [gold(k) for k in range(10)]


def test_perfect_output():
    r = run_score([ok([pred(k) for k in range(10)])], GOLD10)
    assert r["metrics"]["joint"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert r["metrics"]["extraction"]["f1"] == 1.0 and r["metrics"]["coverage"] == 1.0
    d = r["diagnostics"]
    assert not d["missed_not_extracted"] and not d["wrong_label"] and not d["unmatched_over_extraction"]


def test_metric_arithmetic_g10_p10_m8_c7():
    claims = [pred(k) for k in range(8)] + [pred(10), pred(11)]
    claims[0] = pred(0, "unknown")
    r = run_score([ok(claims)], GOLD10)
    c = r["counts"]
    assert (c["gold_claims"], c["predicted_claims"], c["matched"], c["correct"]) == (10, 10, 8, 7)
    assert r["metrics"]["extraction"] == {"precision": 0.8, "recall": 0.8, "f1": 0.8}
    assert r["metrics"]["joint"] == {"precision": 0.7, "recall": 0.7, "f1": 0.7}
    assert r["metrics"]["coverage"] == 0.7


def test_missed_claims():
    r = run_score([ok([pred(k) for k in range(6)])], GOLD10)
    assert r["metrics"]["extraction"]["recall"] == 0.6 and r["metrics"]["extraction"]["precision"] == 1.0
    assert len(r["diagnostics"]["missed_not_extracted"]) == 4
    assert r["diagnostics"]["missed_answer_errored"] == []


def test_extracted_advice_sentence_is_over_extraction():
    r = run_score([ok([pred(k) for k in range(10)] + [pred(12)])], GOLD10)
    assert r["metrics"]["extraction"]["precision"] == round(10 / 11, 4)
    assert r["diagnostics"]["unmatched_over_extraction"] == [pred(12)["claim_id"]]
    assert r["diagnostics"]["unmatched_boundary_error"] == []


def test_boundary_error_overlaps_gold_without_matching():
    start, end = span(0)
    shifted = {**pred(0), "end_char": end - 1, "quote": SENTS[0][:-1], "claim_id": f"S1:{start}:{end - 1}"}
    r = run_score([ok([shifted] + [pred(k) for k in range(1, 10)])], GOLD10)
    assert r["diagnostics"]["unmatched_boundary_error"] == [shifted["claim_id"]]
    assert r["diagnostics"]["missed_not_extracted"] == [GOLD10[0].claim_id]


def test_wrong_labels_confusion_and_tags():
    claims = [pred(k) for k in range(10)]
    claims[1] = pred(1, "supported")
    r = run_score([ok(claims)], GOLD10)
    assert r["diagnostics"]["wrong_label"] == [
        {"claim_id": GOLD10[1].claim_id, "expected": "contradicted", "predicted": "supported"}]
    assert r["diagnostics"]["confusion"]["contradicted"]["supported"] == 1
    assert r["diagnostics"]["per_tag"]["price"] == {"gold": 10, "correct": 9, "missed": 0, "wrong_label": 1}


def test_provider_error_answer_keeps_its_gold_as_missed():
    golds = GOLD10 + [gold(k, aid="S2") for k in range(10)]
    r = run_score([ok([pred(k) for k in range(10)]), err("S2", "provider_error")], golds)
    assert r["counts"]["gold_claims"] == 20 and r["counts"]["predicted_claims"] == 10
    assert r["counts"]["errors_by_type"] == {"provider_error": 1}
    assert len(r["diagnostics"]["missed_answer_errored"]) == 10 and r["diagnostics"]["missed_not_extracted"] == []
    assert r["metrics"]["extraction"]["recall"] == 0.5 and r["metrics"]["answer_errors"] == 1


def test_valid_empty_answer_scores_zero_not_null():
    r = run_score([ok([])], GOLD10)
    assert r["metrics"]["joint"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert len(r["diagnostics"]["missed_not_extracted"]) == 10


def test_no_gold_gives_null_metrics():
    assert run_score([ok([])], [])["metrics"] is None


def test_scheduled_answers_must_match_outcomes():
    a = answers("S1", "S2")
    with pytest.raises(ValueError):
        harness.score("development", ["S1", "S2"], [ok([])], a, GOLD10)
    with pytest.raises(ValueError):
        harness.score("development", ["S1"], [ok([]), ok([])], a, GOLD10)
    with pytest.raises(ValueError):
        harness.score("development", ["S1", "S1"], [ok([]), ok([])], a, GOLD10)
    with pytest.raises(ValueError):
        harness.score("development", ["S1"], [ok([], aid="S2")], a, GOLD10)


def test_bad_predictions_raise_instead_of_being_dropped():
    wrong_quote = {**pred(0), "quote": "not the sentence"}
    bad_id = {**pred(0), "claim_id": "S1:0:1"}
    for claims in ([wrong_quote], [bad_id], [pred(0), pred(0)]):
        with pytest.raises(ValueError):
            run_score([ok(claims)], GOLD10)
    with pytest.raises(ValueError):
        run_score([{**err(), "claims": [pred(0)]}], GOLD10)


def test_check_split_has_null_quality_metrics():
    r = run_score([ok([pred(0)]), err("S2")], [], split="check")
    assert r["metrics"] is None and r["diagnostics"] is None and r["matches"] == {}
    c = r["counts"]
    assert (c["predicted_claims"], c["ok"], c["errors"], c["errors_by_type"]) == (1, 1, 1, {"timeout": 1})
    assert c["gold_claims"] is None and c["matched"] is None and c["correct"] is None
    with pytest.raises(ValueError):
        run_score([ok([{**pred(0), "quote": "x"}])], [], split="check")


def test_scoring_twice_is_byte_identical():
    outcomes = [ok([pred(k) for k in range(8)] + [pred(12)])]

    def dump():
        return json.dumps(run_score(outcomes, GOLD10), sort_keys=True)

    assert dump() == dump()


def run_dict(version, outcomes, golds, model="m"):
    r = run_score(outcomes, golds)
    config = {"dataset_version": "d", "fact_version": "f", "evaluator_version": "e", "provider": "P",
              "model": model, "temperature": 0, "seed": 7, "timeout_s": 60, "max_turns": 3, "max_tokens": 8192,
              "file_hashes": {"x": "1"}, "answer_ids": [o["answer_id"] for o in outcomes],
              "prompt_sha256": version}
    return {"run_id": version, "split": "development", "agent_version": version, "status": "completed",
            "config": config, "counts": r["counts"], "metrics": r["metrics"],
            "answers": [{"answer_id": o["answer_id"],
                         "claims": [{**c, "match": r["matches"].get(c["claim_id"])} for c in o["claims"]]}
                        for o in outcomes]}, r


def two_runs():
    golds = [gold(k) for k in range(9)]
    golds[5], golds[6] = gold(5, "contradicted"), gold(6, "unknown")
    a_claims = [pred(k) for k in range(5)] + [pred(5, "supported")]
    b_claims = [pred(k) for k in range(4)] + [pred(4, "supported"), pred(5, "contradicted"),
                                              pred(6, "supported"), pred(8)]
    return run_dict("v1", [ok(a_claims)], golds), run_dict("v2", [ok(b_claims)], golds), golds


def test_compare_reports_transitions_and_deltas():
    (run_a, _), (run_b, _), golds = two_runs()
    result = harness.compare(run_a, run_b, golds)
    ids = {k: {m["claim_id"] for m in v} for k, v in result["transitions"].items()}
    cid = lambda *ks: {golds[k].claim_id for k in ks}
    assert ids["fixed"] == cid(5, 8)
    assert ids["regressed"] == cid(4)
    assert ids["still_wrong"] == cid(6, 7)
    assert ids["still_right"] == cid(0, 1, 2, 3)
    d = result["deltas"]["joint_f1"]
    assert d["delta"] == round(d["b"] - d["a"], 4) and d["b"] > d["a"]
    assert "## regressed (1)" in harness.render_comparison(result)


def test_compare_refuses_mismatched_settings_or_unfinished_runs():
    (run_a, _), (run_b, _), golds = two_runs()
    run_b["config"]["model"] = "other"
    with pytest.raises(ValueError, match="model"):
        harness.compare(run_a, run_b, golds)
    run_b["config"]["model"] = "m"
    run_b["split"] = "check"
    with pytest.raises(ValueError, match="split"):
        harness.compare(run_a, run_b, golds)
    run_b["split"] = "development"
    run_b["status"] = "failed"
    with pytest.raises(ValueError):
        harness.compare(run_a, run_b, golds)


def test_reports_are_written(tmp_path):
    (run, result), _, _ = two_runs()
    run["run_id"] = "r1"
    harness.write_reports(tmp_path, run, result["diagnostics"])
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Confusion matrix" in report and "Per difficulty tag" in report and "joint" in report
    assert json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))["diagnostics"] is not None
    assert "withheld" in harness.render_report({**run, "split": "check", "metrics": None}, None)
