import pytest

from conftest import claim, part
from claimagent.errors import AgentError
from claimagent.spans import derive_label, finalize

TEXT = "Alpha costs 50 dollars. Pick any colour. Alpha costs 50 dollars. Beta has Wi-Fi."
RETRIEVED = {"f1", "f2"}


def run(claims, text=TEXT):
    return finalize(claims, text, "A99", RETRIEVED)


def bad(claims, text=TEXT):
    with pytest.raises(AgentError) as e:
        run(claims, text)
    assert e.value.kind == "invalid_output"


EST = part("established", ["f1"])
REF = part("refuted", ["f2"])
NIF = part("not_in_facts")


@pytest.mark.parametrize("parts,label", [
    ([EST, EST], "supported"),
    ([EST, REF], "contradicted"),
    ([REF, NIF], "contradicted"),
    ([EST, NIF], "unknown"),
    ([NIF], "unknown"),
])
def test_derive_label(parts, label):
    assert derive_label(parts) == label


def test_offsets_ids_label_and_fact_union():
    [c] = run([claim("Beta has Wi-Fi.", [part("established", ["f2"]), part("refuted", ["f1", "f2"])])])
    assert (c["start_char"], c["end_char"]) == (TEXT.index("Beta"), len(TEXT))
    assert c["claim_id"] == f"A99:{c['start_char']}:{c['end_char']}"
    assert c["label"] == "contradicted" and c["fact_ids"] == ["f1", "f2"]


def test_outer_whitespace_is_stripped_before_locating():
    [c] = run([claim("  Pick any colour.\n", [NIF])])
    assert c["quote"] == "Pick any colour." and TEXT[c["start_char"]:c["end_char"]] == c["quote"]


def test_repeated_quote_resolved_by_occurrence():
    starts = [run([claim("Alpha costs 50 dollars.", [EST], occurrence=n)])[0]["start_char"] for n in (1, 2)]
    assert starts == [0, TEXT.rindex("Alpha")]


@pytest.mark.parametrize("occurrence", [0, 3, -1])
def test_occurrence_out_of_range(occurrence):
    bad([claim("Alpha costs 50 dollars.", [EST], occurrence=occurrence)])


def test_quote_not_found_and_not_normalized():
    bad([claim("Alpha costs 60 dollars.", [EST])])
    bad([claim("alpha costs 50 dollars.", [EST])])


def test_duplicate_claims_rejected():
    bad([claim("Pick any colour.", [NIF]), claim("Pick any colour.", [NIF])])


def test_overlapping_claims_rejected():
    bad([claim("Alpha costs 50 dollars. Pick any colour.", [NIF]), claim("Pick any colour.", [NIF])])


def test_unsorted_claims_are_sorted():
    claims = run([claim("Beta has Wi-Fi.", [NIF]), claim("Pick any colour.", [NIF])])
    assert [c["quote"] for c in claims] == ["Pick any colour.", "Beta has Wi-Fi."]


def test_empty_claims_are_valid():
    assert run([]) == []


@pytest.mark.parametrize("parts", [
    [], "x", [part("maybe")], [part("established")], [part("refuted")],
    [part("established", ["f9"])], [part("established", ["f1", "f3"])],
])
def test_bad_parts(parts):
    bad([claim("Pick any colour.", parts)])


@pytest.mark.parametrize("reason", ["", "   ", "One. Two. Three.", "One! Two? Three."])
def test_bad_reason(reason):
    bad([claim("Pick any colour.", [NIF], reason=reason)])


def test_two_sentence_reason_is_fine():
    assert run([claim("Pick any colour.", [NIF], reason="First. Second.")])


@pytest.mark.parametrize("raw", [{"quote": "Pick any colour."}, "text", None,
                                 {"quote": 5, "occurrence": 1, "parts": [NIF], "reason": "ok."}])
def test_schema_mismatch(raw):
    bad([raw])


def test_claims_must_be_a_list():
    bad({"quote": "x"})
