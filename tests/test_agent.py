import json

import pytest

from claimagent.agent import TOOL, execute_tool
from claimagent.errors import AgentError


@pytest.mark.parametrize("brand", ["cleartrail", "stonewave", "cloudnote"])
def test_tool_returns_every_row_for_the_brand(brand, facts):
    returned_brand, payload = execute_tool("get_brand_facts", json.dumps({"brand_id": brand}))
    data = json.loads(payload)
    assert returned_brand == brand and data["brand_id"] == brand
    assert data["fact_version"] == "speaker-catalogue-v4"
    assert [r["fact_id"] for r in data["facts"]] == [f.fact_id for f in facts[brand]]
    assert payload == json.dumps(data, separators=(",", ":"))


def test_tool_schema_has_one_string_property():
    params = TOOL["function"]["parameters"]
    assert params["required"] == ["brand_id"] and params["properties"]["brand_id"]["type"] == "string"
    assert "enum" not in params["properties"]["brand_id"]


def test_wrong_tool_name_is_illegal():
    with pytest.raises(AgentError) as e:
        execute_tool("search_web", '{"brand_id":"cleartrail"}')
    assert e.value.kind == "illegal_tool"


@pytest.mark.parametrize("raw", ["{not json", "[]", "{}", '{"brand_id":1}',
                                 '{"brand_id":"cleartrail","extra":1}', "null"])
def test_bad_tool_arguments_are_invalid_output(raw):
    with pytest.raises(AgentError) as e:
        execute_tool("get_brand_facts", raw)
    assert e.value.kind == "invalid_output"


def test_unknown_brand_is_rejected():
    with pytest.raises(AgentError) as e:
        execute_tool("get_brand_facts", '{"brand_id":"rivalsound"}')
    assert e.value.kind == "unknown_requested_brand"
