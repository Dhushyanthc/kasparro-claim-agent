import json
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import claim, final_turn, part, tool_turn
from claimagent import api, db, harness, runner
from claimagent.config import settings
from claimagent.data import Answer
from claimagent.errors import AgentError
from claimagent.provider import FakeProvider

TEXT = "The Alpha ships without a charger. Pick any colour."
BODY = {"answer_id": "A99", "brand_id": "cleartrail", "question": "q", "ai_answer": TEXT, "agent_version": "v1"}


@pytest.fixture
def client():
    api.app.dependency_overrides[api.get_provider] = lambda: FakeProvider([])
    yield TestClient(api.app, raise_server_exceptions=False)
    api.app.dependency_overrides.clear()


@pytest.fixture
def provide(client):
    def use(script):
        provider = FakeProvider(script)
        api.app.dependency_overrides[api.get_provider] = lambda: provider
        return provider
    return use


@pytest.fixture
def conn():
    try:
        connection = db.connect()
        db.apply_schema(connection)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL is not reachable; start it with `make db`")
    created = []
    connection.created = created
    yield connection
    for run_id in created:
        connection.execute("DELETE FROM runs WHERE run_id = %s", (run_id,))
    connection.close()


@pytest.fixture
def new_run(conn):
    def create(split="development"):
        run_id = uuid4()
        conn.created.append(run_id)
        db.create_run(conn, run_id, split, "v1", {"k": "v"})
        return run_id
    return create


def assert_error(response, status, type_):
    assert response.status_code == status
    body = response.json()
    assert list(body) == ["error"] and set(body["error"]) >= {"type", "message"}
    assert body["error"]["type"] == type_


def test_real_inputs_fit_the_request_limits(answers):
    assert all(len(a.ai_answer) <= 20000 and len(a.question) <= 4000 for a in answers.values())


def test_classify_happy_path(client, provide, facts):
    fid = facts["cleartrail"][0].fact_id
    provide([tool_turn(), final_turn([claim("The Alpha ships without a charger.", [part("established", [fid])])])])
    r = client.post("/classify", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["answer_id"] == "A99" and body["agent_version"] == "v1"
    assert body["claims"][0]["label"] == "supported" and body["claims"][0]["claim_id"] == "A99:0:34"


def test_classify_with_no_claims(client, provide):
    provide([tool_turn(), final_turn([])])
    assert client.post("/classify", json=BODY).json()["claims"] == []


@pytest.mark.parametrize("change", [
    {"claims": []}, {"expected_label": "supported"}, {"start_char": 1}, {"evidence_fact_ids": []},
    {"difficulty_tags": []}, {"agent_version": "v3"}, {"ai_answer": ""}, {"answer_id": ""},
    {"question": "q" * 4001}, {"ai_answer": "a" * 20001},
])
def test_classify_rejects_bad_bodies(client, change):
    r = client.post("/classify", json={**BODY, **change})
    assert_error(r, 422, "validation_error")


def test_classify_rejects_a_missing_field_without_echoing_the_body(client):
    body = {k: v for k, v in BODY.items() if k != "brand_id"}
    r = client.post("/classify", json={**body, "claims": "SECRET-VALUE"})
    assert_error(r, 422, "validation_error") and "SECRET-VALUE" not in r.text


def test_classify_does_not_strip_whitespace(client, provide):
    provider = provide([tool_turn(), final_turn([])])
    padded = "  " + TEXT + "\n"
    client.post("/classify", json={**BODY, "ai_answer": padded})
    assert padded in provider.requests[0]["messages"][1]["content"]


def test_classify_unknown_brand_is_404_and_never_calls_the_model(client, provide):
    provider = provide([])
    assert_error(client.post("/classify", json={**BODY, "brand_id": "rivalsound"}), 404, "unknown_brand")
    assert provider.requests == []


def test_classify_invalid_output_is_502(client, provide):
    provide([tool_turn(), final_turn([claim("missing quote text", [part("not_in_facts")])])])
    assert_error(client.post("/classify", json=BODY), 502, "invalid_output")


@pytest.mark.parametrize("script,status,type_", [
    ([AgentError("timeout", "slow")], 504, "timeout"),
    ([AgentError("provider_error", "boom")], 502, "provider_error"),
    ([tool_turn(name="other")], 502, "illegal_tool"),
    ([tool_turn(brand="rivalsound")], 502, "unknown_requested_brand"),
    ([tool_turn()] * 3, 502, "turn_limit"),
])
def test_classify_error_statuses(client, provide, script, status, type_):
    provide(script)
    assert_error(client.post("/classify", json=BODY), status, type_)


def test_unexpected_error_is_a_generic_500(client, provide):
    provide([RuntimeError("secret internal detail")])
    r = client.post("/classify", json=BODY)
    assert_error(r, 500, "internal_error")
    assert "secret" not in r.text and "Traceback" not in r.text


def three_dev_answers(answers, monkeypatch):
    chosen = {i: answers[i] for i in ("A01", "A02", "A03")}
    monkeypatch.setattr(runner, "load_answers", lambda: chosen)
    return chosen


def first_sentence(text):
    return text[:text.index(". ") + 1]


def test_run_endpoint_stores_ok_empty_and_error_answers(client, provide, conn, answers, monkeypatch):
    a1, a2, a3 = three_dev_answers(answers, monkeypatch).values()
    provide([tool_turn(a1.brand_id), final_turn([claim(first_sentence(a1.ai_answer), [part("not_in_facts")])]),
             tool_turn(a2.brand_id), final_turn([]),
             AgentError("provider_error", "boom")])
    r = client.post("/evaluation-runs", json={"agent_version": "v1", "split": "development"})
    assert r.status_code == 201
    created = r.json()
    conn.created.append(created["run_id"])
    assert created["status"] == "completed" and created["metrics"] is not None
    assert (created["counts"]["answers"], created["counts"]["ok"], created["counts"]["errors"]) == (3, 2, 1)
    assert created["counts"]["errors_by_type"] == {"provider_error": 1}

    got = client.get(f"/evaluation-runs/{created['run_id']}")
    assert got.status_code == 200
    run = got.json()
    assert [a["answer_id"] for a in run["answers"]] == ["A01", "A02", "A03"]
    assert [a["position"] for a in run["answers"]] == [1, 2, 3]
    assert [(a["status"], a["claim_count"], len(a["claims"])) for a in run["answers"]] == \
        [("ok", 1, 1), ("ok", 0, 0), ("error", 0, 0)]
    assert run["answers"][2]["error_type"] == "provider_error" and run["answers"][2]["claims"] == []
    assert run["answers"][0]["claims"][0]["quote"] == first_sentence(a1.ai_answer)
    assert run["config"]["agent_version"] == "v1" and run["config"]["prompt_sha256"]
    assert client.get(f"/evaluation-runs/{created['run_id']}").json() == run


def test_check_split_run_has_null_metrics(client, provide, conn, monkeypatch):
    chosen = {"C01": Answer("C01", "check", "cleartrail", "q", TEXT)}
    monkeypatch.setattr(runner, "load_answers", lambda: chosen)
    provide([tool_turn(), final_turn([claim("Pick any colour.", [part("not_in_facts")])])])
    r = client.post("/evaluation-runs", json={"agent_version": "v1", "split": "check"})
    assert r.status_code == 201 and r.json()["metrics"] is None
    conn.created.append(r.json()["run_id"])
    assert r.json()["counts"]["predicted_claims"] == 1 and r.json()["counts"]["gold_claims"] is None


def test_run_endpoint_rejects_bad_bodies(client):
    assert_error(client.post("/evaluation-runs", json={"agent_version": "v1"}), 422, "validation_error")
    assert_error(client.post("/evaluation-runs", json={"agent_version": "v1", "split": "x"}), 422, "validation_error")


def test_failed_run_reports_run_id_and_marks_the_run_failed(client, provide, conn, answers, monkeypatch):
    three_dev_answers(answers, monkeypatch)
    provide([tool_turn("cleartrail"), RuntimeError("bug")])
    r = client.post("/evaluation-runs", json={"agent_version": "v1", "split": "development"})
    assert_error(r, 500, "run_failed")
    run_id = r.json()["error"]["run_id"]
    conn.created.append(run_id)
    stored = client.get(f"/evaluation-runs/{run_id}").json()
    assert stored["status"] == "failed" and stored["error"] == "RuntimeError"


def test_get_missing_run_is_404(client, conn):
    assert_error(client.get(f"/evaluation-runs/{uuid4()}"), 404, "not_found")


def test_get_invalid_uuid_is_422(client):
    assert_error(client.get("/evaluation-runs/not-a-uuid"), 422, "validation_error")


def test_database_down_is_503(client, provide, monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://claims:claims@localhost:1/claims")
    assert_error(client.get(f"/evaluation-runs/{uuid4()}"), 503, "database_unavailable")
    provide([])
    assert_error(client.post("/evaluation-runs", json={"agent_version": "v1", "split": "check"}),
                 503, "database_unavailable")


def outcome(answer_id="A1", claims=(), status="ok", error_type=None):
    return {"answer_id": answer_id, "status": status, "error_type": error_type,
            "error_message": error_type and "m", "claims": list(claims), "latency_ms": 3}


def stored_claim(start, end, claim_id=None, label="unknown"):
    return {"claim_id": claim_id or f"A1:{start}:{end}", "start_char": start, "end_char": end, "quote": "q",
            "label": label, "fact_ids": ["a.b"], "reason": "r.", "parts": [{"status": "not_in_facts"}]}


def test_round_trip_keeps_parts_and_fact_ids(conn, new_run):
    run_id = new_run()
    db.save_answer(conn, run_id, 1, outcome(claims=[stored_claim(5, 9), stored_claim(0, 4)]), None)
    db.set_matches(conn, run_id, {"A1:0:4": {"gold_claim_id": "g", "correct": True}})
    run = db.get_run(conn, run_id)
    claims = run["answers"][0]["claims"]
    assert [c["start_char"] for c in claims] == [0, 5]
    assert claims[0]["match"] == {"gold_claim_id": "g", "correct": True} and claims[1]["match"] is None
    assert claims[0]["parts"] == [{"status": "not_in_facts"}] and claims[0]["fact_ids"] == ["a.b"]


def test_duplicate_answer_in_a_run_is_rejected(conn, new_run):
    run_id = new_run()
    db.save_answer(conn, run_id, 1, outcome(), None)
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.save_answer(conn, run_id, 2, outcome(), None)


def test_duplicate_span_is_rejected_and_rolls_back_the_answer(conn, new_run):
    run_id = new_run()
    dup = [stored_claim(0, 4), stored_claim(0, 4, claim_id="A1:other")]
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.save_answer(conn, run_id, 1, outcome(claims=dup), None)
    assert db.get_run(conn, run_id)["answers"] == []


def test_duplicate_claim_id_is_rejected(conn, new_run):
    run_id = new_run()
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.save_answer(conn, run_id, 1, outcome(claims=[stored_claim(0, 4), stored_claim(6, 9, claim_id="A1:0:4")]), None)


def test_errored_answer_cannot_hold_claims(conn, new_run):
    run_id = new_run()
    with pytest.raises(psycopg.errors.CheckViolation):
        db.save_answer(conn, run_id, 1, outcome(claims=[stored_claim(0, 4)], status="error", error_type="timeout"), None)


def test_run_lifecycle_and_sql_injection_safety(conn, new_run):
    run_id = new_run()
    nasty = "x'; DROP TABLE runs; --"
    db.save_answer(conn, run_id, 1, outcome(claims=[{**stored_claim(0, 4), "quote": nasty}]), None)
    db.fail_run(conn, run_id, nasty)
    run = db.get_run(conn, run_id)
    assert run["status"] == "failed" and run["error"] == nasty and run["answers"][0]["claims"][0]["quote"] == nasty
    assert run["finished_at"] is not None and json.dumps(run["config"])


def test_runner_writes_reports_and_compare_works_on_stored_runs(conn, answers, monkeypatch, tmp_path):
    a1, a2 = answers["A01"], answers["A02"]

    def script(first_claims):
        return [tool_turn(a1.brand_id), final_turn(first_claims), AgentError("timeout", "slow")]

    runs = []
    for name, claims in (("one", []), ("two", [claim(first_sentence(a1.ai_answer), [part("not_in_facts")])])):
        run_id = runner.run_split("v1", "development", FakeProvider(script(claims)), answer_ids=["A01", "A02"],
                                  out_dir=tmp_path / name)
        conn.created.append(run_id)
        runs.append(db.get_run(conn, run_id))
        folder = tmp_path / name
        assert {p.name for p in folder.iterdir()} == {"run.json", "report.md", "exchanges.jsonl"}
        lines = [json.loads(line) for line in (folder / "exchanges.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [(x["answer_id"], x["status"]) for x in lines] == [("A01", "ok"), ("A02", "error")]
        assert lines[0]["exchange"]["messages"][-1]["role"] == "tool" and lines[1]["error_type"] == "timeout"
        assert runs[-1]["answers"][1]["trace_ref"] == "exchanges.jsonl#A02"
        assert "Confusion matrix" in (folder / "report.md").read_text(encoding="utf-8")
    result = harness.compare(*runs)
    assert result["deltas"]["extraction_precision"]["a"] == 0.0
    assert harness.render_comparison(result).startswith("# Comparison v1 vs v1")
