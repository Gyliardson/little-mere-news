import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("lmn_harvester", MODULE_PATH)
harvester = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(harvester)


def test_clean_html_removes_markup_and_normalizes_text():
    assert harvester.clean_html("<p>Hello <strong>world</strong></p>") == "Hello world"


def test_clean_html_rejects_non_string_input():
    assert harvester.clean_html(None) == ""


def test_parse_date_falls_back_for_missing_or_invalid_date():
    fallback = datetime(2026, 8, 12, 22, 15, 0)
    assert harvester.parse_date(SimpleNamespace(), now=fallback) == fallback
    invalid = SimpleNamespace(published_parsed=(999999, 99, 99, 99, 99, 99, 0, 0, 0))
    assert harvester.parse_date(invalid, now=fallback) == fallback


def test_validate_ai_result_accepts_only_required_non_empty_strings():
    valid = {
        "title_en": "English title",
        "title_pt": "Titulo em portugues",
        "summary_en": "English summary",
        "summary_pt": "Resumo em portugues",
        "ignored": "extra",
    }
    assert harvester.validate_ai_result(valid) == {
        key: valid[key] for key in harvester.AI_REQUIRED_FIELDS
    }


def test_validate_ai_result_rejects_missing_empty_or_wrong_type_fields():
    base = {
        "title_en": "English title",
        "title_pt": "Titulo em portugues",
        "summary_en": "English summary",
        "summary_pt": "Resumo em portugues",
    }
    for mutation in (
        {**base, "title_en": ""},
        {**base, "summary_pt": None},
        {key: value for key, value in base.items() if key != "title_pt"},
        [base],
    ):
        assert harvester.validate_ai_result(mutation) is None


def test_decode_ollama_response_handles_success_and_malformed_payloads():
    valid = {
        "title_en": "English title",
        "title_pt": "Titulo em portugues",
        "summary_en": "English summary",
        "summary_pt": "Resumo em portugues",
    }
    assert harvester.decode_ollama_response({"response": json.dumps(valid)}) == valid
    assert harvester.decode_ollama_response({"response": "not-json"}) is None
    assert harvester.decode_ollama_response({"response": json.dumps({"title_en": "partial"})}) is None
    assert harvester.decode_ollama_response({}) is None
