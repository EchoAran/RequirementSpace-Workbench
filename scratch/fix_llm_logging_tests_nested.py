from pathlib import Path

test_file = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/tests/services/test_llm_logging.py")
content = test_file.read_text(encoding="utf-8")

# Let's clean up the DEBUG_HIERARCHY block we added
original_debug_block = """    # Print logging hierarchy state
    import sys
    curr = logging.getLogger("backend.services.llm_handler_service")
    while curr:
        print(f"DEBUG_HIERARCHY: Logger name='{curr.name}' level={logging.getLevelName(curr.level)} propagate={curr.propagate} handlers={curr.handlers}", file=sys.stderr)
        curr = curr.parent
    print(f"DEBUG_HIERARCHY: Root logger level={logging.getLevelName(logging.getLogger().level)} handlers={logging.getLogger().handlers}", file=sys.stderr)"""

content = content.replace(original_debug_block, "")

# Now replace:
# caplog.at_level(logging.INFO, logger="backend.services.llm_handler_service")
# with:
# caplog.at_level(logging.INFO), caplog.at_level(logging.INFO, logger="backend")
content = content.replace(
    'caplog.at_level(logging.INFO, logger="backend.services.llm_handler_service")',
    'caplog.at_level(logging.INFO), caplog.at_level(logging.INFO, logger="backend")'
)

# And for ERROR:
content = content.replace(
    'caplog.at_level(logging.ERROR, logger="backend.services.llm_handler_service")',
    'caplog.at_level(logging.ERROR), caplog.at_level(logging.ERROR, logger="backend")'
)

test_file.write_text(content, encoding="utf-8")
print("Updated test_llm_logging.py successfully!")

# Do the same for test_llm_logging_hardening.py
hardening_file = Path("e:/PycharmProjects/RequirementSpace-Workbench/backend/tests/core/security/test_llm_logging_hardening.py")
h_content = hardening_file.read_text(encoding="utf-8")

h_content = h_content.replace(
    'caplog.at_level(logging.INFO, logger="backend.services.llm_handler_service")',
    'caplog.at_level(logging.INFO), caplog.at_level(logging.INFO, logger="backend")'
)
h_content = h_content.replace(
    'caplog.at_level(logging.ERROR, logger="backend.services.llm_handler_service")',
    'caplog.at_level(logging.ERROR), caplog.at_level(logging.ERROR, logger="backend")'
)

hardening_file.write_text(h_content, encoding="utf-8")
print("Updated test_llm_logging_hardening.py successfully!")
