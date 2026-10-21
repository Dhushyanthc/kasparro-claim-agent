import json
from collections import Counter
from pathlib import Path

from .data import Answer
from .gold import Gold, load_gold

LABELS = ("supported", "contradicted", "unknown")
COMPARE_KEYS = ("split", "dataset_version", "fact_version", "evaluator_version", "provider", "model",
                "temperature", "seed", "timeout_s", "max_turns", "max_tokens", "file_hashes", "answer_ids")
METRIC_PATHS = [(g, m) for g in ("extraction", "joint") for m in ("precision", "recall", "f1")] + \
    [("coverage", None)]


def ratio(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def prf(hits: int, predicted: int, gold: int) -> dict:
    return {"precision": ratio(hits, predicted), "recall": ratio(hits, gold),
            "f1": ratio(2 * hits, predicted + gold)}


def predictions(outcomes: list[dict], answers: dict[str, Answer]) -> list[tuple[str, dict]]:
    preds = []
    for o in outcomes:
        if o["status"] == "error" and o["claims"]:
            raise ValueError(f"errored answer {o['answer_id']} has claims")
        ordered = sorted(o["claims"], key=lambda c: c["start_char"])
        for a, b in zip(ordered, ordered[1:]):
            if a["end_char"] > b["start_char"]:
                raise ValueError(f"overlapping claims in {o['answer_id']}")
        for c in ordered:
            text = answers[o["answer_id"]].ai_answer
            if c["quote"] != text[c["start_char"]:c["end_char"]] \
                    or c["claim_id"] != f"{o['answer_id']}:{c['start_char']}:{c['end_char']}":
                raise ValueError(f"invalid claim {c['claim_id']}")
            preds.append((o["answer_id"], c))
    return sorted(preds, key=lambda p: (p[0], p[1]["start_char"]))


def score(split: str, scheduled: list[str], outcomes: list[dict], answers: dict[str, Answer],
          gold: list[Gold] | None = None) -> dict:
    ids = [o["answer_id"] for o in outcomes]
    if len(set(scheduled)) != len(scheduled) or sorted(scheduled) != sorted(ids):
        raise ValueError("outcomes do not match the scheduled answers exactly once")
    preds = predictions(outcomes, answers)
    errors = Counter(o["error_type"] for o in outcomes if o["status"] == "error")
    counts = {"answers": len(outcomes), "ok": len(outcomes) - sum(errors.values()),
              "errors": sum(errors.values()), "errors_by_type": dict(sorted(errors.items())),
              "predicted_claims": len(preds), "gold_claims": None, "matched": None, "correct": None,
              "latency_ms_total": sum(o["latency_ms"] or 0 for o in outcomes)}
    if split == "check":
        return {"counts": counts, "metrics": None, "diagnostics": None, "matches": {}}
    gold = [g for g in (gold if gold is not None else load_gold()) if g.answer_id in scheduled]
    gold_idx = {(g.answer_id, g.start, g.end): g for g in gold}
    matches = {}
    for aid, c in preds:
        g = gold_idx.get((aid, c["start_char"], c["end_char"]))
        if g:
            matches[c["claim_id"]] = {"gold_claim_id": g.claim_id, "expected_label": g.label,
                                      "correct": c["label"] == g.label}
    m, c_ok, g_n, p_n = len(matches), sum(x["correct"] for x in matches.values()), len(gold), len(preds)
    counts.update(gold_claims=g_n, matched=m, correct=c_ok)
    metrics = None
    if g_n:
        metrics = {"extraction": prf(m, p_n, g_n), "joint": prf(c_ok, p_n, g_n),
                   "coverage": ratio(c_ok, g_n), "answer_errors": counts["errors"]}
    return {"counts": counts, "metrics": metrics, "matches": matches,
            "diagnostics": diagnose(gold, preds, matches, outcomes)}


def diagnose(gold: list[Gold], preds: list[tuple[str, dict]], matches: dict, outcomes: list[dict]) -> dict:
    errored = {o["answer_id"] for o in outcomes if o["status"] == "error"}
    label_of = {c["claim_id"]: c["label"] for _, c in preds}
    by_gold = {x["gold_claim_id"]: label_of[cid] for cid, x in matches.items()}
    ordered = sorted(gold, key=lambda g: (g.answer_id, g.start))
    missed = [g for g in ordered if g.claim_id not in by_gold]
    spans = {}
    for g in gold:
        spans.setdefault(g.answer_id, []).append((g.start, g.end))
    unmatched = [(aid, c) for aid, c in preds if c["claim_id"] not in matches]
    boundary = [c["claim_id"] for aid, c in unmatched
                if any(c["start_char"] < e and s < c["end_char"] for s, e in spans.get(aid, []))]
    wrong = [{"claim_id": g.claim_id, "expected": g.label, "predicted": by_gold[g.claim_id]}
             for g in ordered if g.claim_id in by_gold and by_gold[g.claim_id] != g.label]
    confusion = {e: {**{p: 0 for p in LABELS}, "missed": 0} for e in LABELS}
    for g in ordered:
        confusion[g.label][by_gold.get(g.claim_id, "missed")] += 1
    tags = {}
    for g in ordered:
        for t in g.tags:
            row = tags.setdefault(t, {"gold": 0, "correct": 0, "missed": 0, "wrong_label": 0})
            row["gold"] += 1
            if g.claim_id not in by_gold:
                row["missed"] += 1
            elif by_gold[g.claim_id] == g.label:
                row["correct"] += 1
            else:
                row["wrong_label"] += 1
    return {"missed_answer_errored": [g.claim_id for g in missed if g.answer_id in errored],
            "missed_not_extracted": [g.claim_id for g in missed if g.answer_id not in errored],
            "unmatched_boundary_error": boundary,
            "unmatched_over_extraction": [c["claim_id"] for _, c in unmatched if c["claim_id"] not in boundary],
            "wrong_label": wrong, "confusion": confusion, "per_tag": dict(sorted(tags.items()))}


def predicted_labels(run: dict, gold: list[Gold]) -> dict[str, str]:
    matched = {c["match"]["gold_claim_id"]: c["label"]
               for a in run["answers"] for c in a["claims"] if c["match"]}
    return {g.claim_id: matched.get(g.claim_id, "missed") for g in gold}


def compare(run_a: dict, run_b: dict, gold: list[Gold] | None = None) -> dict:
    flat = [{**r["config"], "split": r["split"]} for r in (run_a, run_b)]
    mismatched = [k for k in COMPARE_KEYS if flat[0].get(k) != flat[1].get(k)]
    if mismatched:
        raise ValueError(f"runs are not comparable, differing: {', '.join(mismatched)}")
    if run_a["status"] != "completed" or run_b["status"] != "completed" or run_a["metrics"] is None:
        raise ValueError("both runs must be completed development runs")
    gold = [g for g in (gold if gold is not None else load_gold()) if g.answer_id in flat[0]["answer_ids"]]
    pred_a, pred_b = predicted_labels(run_a, gold), predicted_labels(run_b, gold)
    expected = {g.claim_id: g.label for g in gold}
    moves = {"fixed": [], "regressed": [], "still_wrong": [], "still_right": []}
    for cid, label in sorted(expected.items()):
        key = {(False, True): "fixed", (True, False): "regressed", (False, False): "still_wrong",
               (True, True): "still_right"}[pred_a[cid] == label, pred_b[cid] == label]
        moves[key].append({"claim_id": cid, "expected": label, "a": pred_a[cid], "b": pred_b[cid]})
    deltas = {}
    for group, key in METRIC_PATHS:
        a, b = (r["metrics"][group] if key is None else r["metrics"][group][key] for r in (run_a, run_b))
        deltas[group if key is None else f"{group}_{key}"] = {"a": a, "b": b, "delta": round(b - a, 4)}
    return {"a": run_a["run_id"], "b": run_b["run_id"], "versions": [run_a["agent_version"], run_b["agent_version"]],
            "deltas": deltas, "answer_errors": [run_a["metrics"]["answer_errors"], run_b["metrics"]["answer_errors"]],
            "transitions": moves}


def table(headers: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + \
        ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def render_report(run: dict, diagnostics: dict | None) -> str:
    cfg, counts = run["config"], run["counts"]
    out = [f"# Run {run['run_id']}", "",
           f"split `{run['split']}` · agent `{run['agent_version']}` · model `{cfg['model']}` · "
           f"prompt sha256 `{cfg['prompt_sha256']}`", "", "## Counts", ""]
    out += table(["answers", "ok", "errors", "predicted claims", "gold claims", "matched", "correct"],
                 [[counts[k] for k in ("answers", "ok", "errors", "predicted_claims", "gold_claims", "matched", "correct")]])
    out += ["", f"Answer errors by type: {counts['errors_by_type'] or 'none'}", ""]
    if run["metrics"] is None:
        return "\n".join(out + ["Quality metrics are withheld for the check split."]) + "\n"
    m = run["metrics"]
    out += ["## Metrics (joint F1 is the headline)", ""]
    out += table(["", "precision", "recall", "f1"],
                 [[g, *(m[g][k] for k in ("precision", "recall", "f1"))] for g in ("extraction", "joint")])
    out += ["", f"Coverage (correct / gold): {m['coverage']} · answer errors: {m['answer_errors']}", "",
            "## Diagnostics", ""]
    for key, ids in diagnostics.items():
        if isinstance(ids, list) and key != "wrong_label":
            out.append(f"- {key} ({len(ids)}): {', '.join(ids) or 'none'}")
    out += [f"- wrong_label ({len(diagnostics['wrong_label'])}): "
            + (", ".join(f"{w['claim_id']} (expected {w['expected']}, got {w['predicted']})"
                         for w in diagnostics["wrong_label"]) or "none"), "", "### Confusion matrix (rows expected)", ""]
    out += table(["expected \\ predicted", *LABELS, "missed"],
                 [[e, *(diagnostics["confusion"][e][c] for c in (*LABELS, "missed"))] for e in LABELS])
    out += ["", "### Per difficulty tag", ""]
    out += table(["tag", "gold", "correct", "missed", "wrong label"],
                 [[t, *r.values()] for t, r in diagnostics["per_tag"].items()])
    return "\n".join(out) + "\n"


def render_comparison(result: dict) -> str:
    a, b = result["versions"]
    out = [f"# Comparison {a} vs {b} (development)", "", f"run A `{result['a']}` · run B `{result['b']}`", ""]
    out += table(["metric", a, b, "delta"], [[k, v["a"], v["b"], v["delta"]] for k, v in result["deltas"].items()])
    out += ["", f"Answer errors: {a} {result['answer_errors'][0]}, {b} {result['answer_errors'][1]}", ""]
    for key, items in result["transitions"].items():
        out += [f"## {key} ({len(items)})", ""]
        if key in ("fixed", "regressed"):
            out += table(["claim", "expected", a, b], [[i["claim_id"], i["expected"], i["a"], i["b"]] for i in items]) \
                if items else ["none"]
        out.append("")
    return "\n".join(out)


def write_reports(out_dir: Path, run: dict, diagnostics: dict | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {**run, "diagnostics": diagnostics}
    (out_dir / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n",
                                      encoding="utf-8", newline="\n")
    (out_dir / "report.md").write_text(render_report(run, diagnostics), encoding="utf-8", newline="\n")
