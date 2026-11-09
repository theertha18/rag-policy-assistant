from app.guardrails.output_validator import validate_output

EMEA = "Region: EMEA; Laptop Allowance (Max): €1,800 EUR; Monthly Mobile Stipend: €60 EUR"
HOME = "The home office stipend has been increased to $750 USD per calendar year."
SOURCES = {"S1": EMEA, "S2": HOME}
MARKER = "LM-abcdef"


# ---------- Original tests ----------

def test_correct_answer_passes():
    assert validate_output("The laptop allowance is €1,800 and the stipend is €60.", ["S1"], SOURCES, MARKER) == []


def test_invented_number_is_rejected():
    assert validate_output("The laptop allowance is €2,500.", ["S1"], SOURCES, MARKER) == ["ungrounded_numbers:['2500']"]


def test_number_from_uncited_source_is_rejected():
    errors = validate_output("The allowance is $750.", ["S1"], SOURCES, MARKER)
    assert errors == ["ungrounded_numbers:['750']"]


def test_missing_citations_are_rejected():
    assert "no_citations" in validate_output("Some answer.", [], SOURCES, MARKER)


def test_prompt_leak_is_rejected():
    assert "prompt_leak" in validate_output(f"My rules say {MARKER}", ["S1"], SOURCES, MARKER)


def test_multi_document_answer_passes_when_both_cited():
    answer = "Laptop up to €1,800; home office $750 per year."
    assert validate_output(answer, ["S1", "S2"], SOURCES, MARKER) == []


# ---------- New: labels and list numbering are not facts ----------

def test_source_labels_in_answer_are_not_treated_as_numbers():
    answer = "The laptop allowance is €1,800 (S1)."
    assert validate_output(answer, ["S1"], SOURCES, MARKER) == []


def test_numbered_list_markers_are_not_treated_as_numbers():
    answer = "1. Laptop: €1,800\n2. Home office: $750 per year"
    assert validate_output(answer, ["S1", "S2"], SOURCES, MARKER) == []


def test_invented_number_still_caught_next_to_a_label():
    answer = "The laptop allowance is €2,500 (S1)."
    assert validate_output(answer, ["S1"], SOURCES, MARKER) == ["ungrounded_numbers:['2500']"]