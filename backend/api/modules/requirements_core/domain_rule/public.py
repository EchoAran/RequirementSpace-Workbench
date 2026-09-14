"""Public interfaces exported by the domain rule module."""

from backend.api.modules.requirements_core.domain_rule.application.choice_adapter import (
    RuleGenerationChoiceAdapter,
)
from backend.api.modules.requirements_core.domain_rule.application.domain_rule_service import (
    DomainRuleService,
)
from backend.api.modules.requirements_core.domain_rule.application.rule_generation_service import (
    RuleGenerationService,
)
from backend.api.modules.requirements_core.domain_rule.domain.model_invariants import (
    ALLOWED_RULE_LINK_TARGET_KINDS,
    validate_parent_hierarchy,
    validate_rule_confirmation_status,
    validate_rule_link_purpose,
    validate_rule_link_target,
    validate_rule_origin,
    validate_rule_text,
)
from backend.api.modules.requirements_core.domain_rule.domain.node_resolver import (
    RequirementNodeResolver,
    ResolvedNode,
)
from backend.api.modules.requirements_core.domain_rule.ports import (
    get_domain_rule_service,
    set_domain_rule_service,
)
from backend.api.modules.requirements_core.domain_rule.schemas import (
    DomainRuleCreateRequest,
    DomainRuleListResponse,
    DomainRuleResponse,
    DomainRuleUpdateRequest,
    RuleLinkCreateRequest,
    RuleLinkResponse,
)
from backend.database.model import (
    DomainRuleModel,
    RuleLinkModel,
    RuleLinkPurpose,
    RuleOrigin,
)

__all__ = [
    "ALLOWED_RULE_LINK_TARGET_KINDS",
    "DomainRuleCreateRequest",
    "DomainRuleListResponse",
    "DomainRuleModel",
    "DomainRuleResponse",
    "DomainRuleService",
    "DomainRuleUpdateRequest",
    "RequirementNodeResolver",
    "ResolvedNode",
    "RuleGenerationChoiceAdapter",
    "RuleGenerationService",
    "RuleLinkCreateRequest",
    "RuleLinkModel",
    "RuleLinkPurpose",
    "RuleLinkResponse",
    "RuleOrigin",
    "get_domain_rule_service",
    "set_domain_rule_service",
    "validate_parent_hierarchy",
    "validate_rule_confirmation_status",
    "validate_rule_link_purpose",
    "validate_rule_link_target",
    "validate_rule_origin",
    "validate_rule_text",
]
