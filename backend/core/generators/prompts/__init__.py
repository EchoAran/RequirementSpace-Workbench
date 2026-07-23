from backend.core.prompt_resolver import LocalizedPromptProxy

actors_generate_prompt = LocalizedPromptProxy("actors_generate")
features_generate_prompt = LocalizedPromptProxy("features_generate")
business_object_in_flows_prompt = LocalizedPromptProxy("business_object_in_flows")
business_objects_generate_prompt = LocalizedPromptProxy("business_objects_generate")
flows_generate_prompt = LocalizedPromptProxy("flows_generate")
flows_generate_combined_prompt = LocalizedPromptProxy("flows_generate_combined")
scenarios_generate_prompt = LocalizedPromptProxy("scenarios_generate")
scopes_generate_prompt = LocalizedPromptProxy("scopes_generate")
acceptance_criteria_generate_prompt = LocalizedPromptProxy("acceptance_criteria_generate")
blank_project_generate_prompt = LocalizedPromptProxy("blank_project_generate")
PROJECT_INTERVIEW_SYSTEM_PROMPT = LocalizedPromptProxy("project_interview")
