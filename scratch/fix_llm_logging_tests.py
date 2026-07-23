from pathlib import Path

test_file = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/tests/services/test_llm_logging.py")
content = test_file.read_text(encoding="utf-8")

# Let's clean up the debug print statements we added and make sure os is imported if needed,
# but we don't need the prints anymore if we fix it. Let's restore the original clean asserts.
# Let's replace the block we modified back to its clean original state:
original_block = """    print("DEBUG: result =", result)
    print("DEBUG: caplog records =", caplog.records)
    print("DEBUG: _events =", _events(caplog))
    print("DEBUG: Root level:", logging.getLevelName(logging.getLogger().level))
    print("DEBUG: Backend level:", logging.getLevelName(logging.getLogger("backend").level))
    print("DEBUG: Handler level:", logging.getLevelName(logging.getLogger("backend.services.llm_handler_service").level))
    print("DEBUG: LOG_ENABLED:", os.getenv("LOG_ENABLED"))
    print("DEBUG: LOG_ENABLED_CATEGORIES:", os.getenv("LOG_ENABLED_CATEGORIES"))

    assert result == "model answer secret"
    events = _events(caplog)
    assert any(record.event == "llm_api_call_attempt" for record in events)
    completed = [record for record in events if record.event == "llm_api_call_completed"]
    assert len(completed) == 1"""

clean_block = """    assert result == "model answer secret"
    events = _events(caplog)
    assert any(record.event == "llm_api_call_attempt" for record in events)
    completed = [record for record in events if record.event == "llm_api_call_completed"]
    assert len(completed) == 1"""

content = content.replace(original_block, clean_block)

# Now replace all caplog.at_level(level) with caplog.at_level(level, logger="backend.services.llm_handler_service")
# Wait, let's use simple replacement:
replacements = [
    ("caplog.at_level(logging.INFO)", 'caplog.at_level(logging.INFO, logger="backend.services.llm_handler_service")'),
    ("caplog.at_level(logging.ERROR)", 'caplog.at_level(logging.ERROR, logger="backend.services.llm_handler_service")'),
]

for old, new in replacements:
    content = content.replace(old, new)

test_file.write_text(content, encoding="utf-8")
print("Updated test_llm_logging.py successfully!")

# Now do the same for test_llm_logging_hardening.py
hardening_file = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/tests/core/security/test_llm_logging_hardening.py")
h_content = hardening_file.read_text(encoding="utf-8")

for old, new in replacements:
    h_content = h_content.replace(old, new)

hardening_file.write_text(h_content, encoding="utf-8")
print("Updated test_llm_logging_hardening.py successfully!")
