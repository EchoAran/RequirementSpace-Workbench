"""Presentation rules for natural-language AI replies, separate from machine references."""

import re

AI_USER_TEXT_INSTRUCTION = (
    "In user-facing replies and summaries, refer to objects by their names. "
    "Never disclose internal database IDs, primary keys, logical UUIDs, or reference tokens. "
    "IDs needed by structured machine fields must stay in those fields only. "
    "Preserve business identifiers explicitly supplied by users, quantities, dates, and amounts."
)

_ENTITY = (
    r"actor|feature|flow|business_object(?:_attribute)?|rule|domain_rule|flow_step|scenario"
    r"|acceptance_criterion|perception_slot|scope|project|workspace|session|draft|target|node"
)
_ID = r"(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32}|\d+)"
_VALUE = rf"(?:{_ID}|\[\s*{_ID}(?:\s*,\s*{_ID})*\s*\])"
_REFERENCE = (
    rf"(?:\b(?:parent_|related_)?(?:{_ENTITY})(?:_ids?|_logical_uuid)?\b|(?<!\w)(?:id|logical_uuid)\b"
    r"|内部(?:数据库)?\s*ID|数据库(?:主键|\s*ID)|逻辑\s*UUID"
    r"|(?:参与者|功能|流程|业务对象|业务规则|场景|工作区|会话|草稿)\s*(?:ID|编号|主键))"
    rf"[\s`\"']*(?:[:：=#]|\bis\b|为|是|(?<=\s))[\s`\"']*{_VALUE}(?![\w-])"
)
_INTERNAL_REFERENCE = re.compile(
    rf"[（(]\s*{_REFERENCE}\s*[`\"']*\s*[）)]|{_REFERENCE}[`\"']*",
    re.IGNORECASE,
)
_BUSINESS_ID_PREFIX = re.compile(r"(?:订单|商品|客户|发票|工单|order|product|customer|invoice|ticket)\s*$", re.IGNORECASE)


def format_ai_user_text(text: str) -> str:
    """Omit explicitly marked database references without deleting ordinary numbers."""
    def render_reference(match: re.Match) -> str:
        if re.match(r"[（(]?\s*id\b", match.group(), re.IGNORECASE) and _BUSINESS_ID_PREFIX.search(text[:match.start()]):
            return match.group()
        return ""

    return _INTERNAL_REFERENCE.sub(render_reference, text)
