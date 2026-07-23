from backend.core.prompt_resolver import LocalizedPromptProxy

SYSTEM_PROMPT = LocalizedPromptProxy("business_object_attribute_system")
USER_PROMPT_TEMPLATE = LocalizedPromptProxy("business_object_attribute_user")
