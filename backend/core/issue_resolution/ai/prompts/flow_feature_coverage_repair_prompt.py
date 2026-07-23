from backend.core.prompt_resolver import LocalizedPromptProxy

SYSTEM_PROMPT = LocalizedPromptProxy("flow_feature_coverage_system")
USER_PROMPT_TEMPLATE = LocalizedPromptProxy("flow_feature_coverage_user")
