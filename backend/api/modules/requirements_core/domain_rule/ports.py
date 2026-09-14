"""Ports and runtime registration hooks for the domain rule module."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.api.modules.requirements_core.domain_rule.application.domain_rule_service import (
        DomainRuleService,
    )

_domain_rule_service = None


def get_domain_rule_service() -> "DomainRuleService":
    """Retrieve registered DomainRuleService instance or instantiate default."""
    global _domain_rule_service
    if _domain_rule_service is None:
        from backend.api.modules.requirements_core.domain_rule.application.domain_rule_service import (
            DomainRuleService,
        )

        _domain_rule_service = DomainRuleService()
    return _domain_rule_service


def set_domain_rule_service(service: "DomainRuleService") -> None:
    """Register custom DomainRuleService instance."""
    global _domain_rule_service
    _domain_rule_service = service
