import pytest

from claimagent.data import load_answers, load_facts


@pytest.fixture(scope="session")
def answers():
    return load_answers()


@pytest.fixture(scope="session")
def facts():
    return load_facts()
