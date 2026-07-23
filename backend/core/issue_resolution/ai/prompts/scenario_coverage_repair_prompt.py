from backend.core.prompt_resolver import LocalizedPromptProxy

SYSTEM_PROMPT = LocalizedPromptProxy("scenario_coverage_system")
USER_PROMPT_TEMPLATE = LocalizedPromptProxy("scenario_coverage_user")
