# SPL Semantic Export Skill

This skill performs an LLM-backed semantic conversion of RequirementSpace workbench model outputs into a valid, rich SPL (Structured Prompt Language) DSL agent specification.
It translates flows to workers with inputs/outputs/branches, objects to typed schemas, and ACs to Gherkin scenarios.
It runs as an external skill packaged inside `backend/integration`.
