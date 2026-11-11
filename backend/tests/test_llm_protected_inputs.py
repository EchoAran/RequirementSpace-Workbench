from dataclasses import dataclass

from backend.core.llm_protected_inputs import collect_protected_texts


@dataclass
class _Input:
    requirements: str
    nested: list[dict]


def test_collect_protected_texts_flattens_and_deduplicates_explicit_inputs():
    value = _Input(
        requirements=" English Product Name ",
        nested=[{"name": "微信", "duplicate": "English Product Name"}],
    )

    assert collect_protected_texts(value, "ERP", None, 1) == (
        "English Product Name",
        "微信",
        "ERP",
    )
