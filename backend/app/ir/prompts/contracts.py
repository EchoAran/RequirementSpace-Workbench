from __future__ import annotations

from pydantic import Field

from ..schema import ChoiceGroup, Proposal, RequirementLink, RequirementNode, RequirementSlot, RequirementSpaceIR, StrictModel


class InitializeWorkspaceInput(StrictModel):
    idea: str = Field(min_length=1)


class InitializeWorkspaceOutput(StrictModel):
    ir: RequirementSpaceIR


class ExpandSlotInput(StrictModel):
    slot: RequirementSlot
    ownerNode: RequirementNode
    relatedNodes: list[RequirementNode] = Field(default_factory=list)
    relatedLinks: list[RequirementLink] = Field(default_factory=list)
    projectionContext: str = "system"


class ExpandSlotOutput(StrictModel):
    choiceGroup: ChoiceGroup


class RewriteInput(StrictModel):
    workspaceId: str
    scope: dict[str, object] = Field(default_factory=dict)
    instruction: str = Field(min_length=1)
    irSlice: dict[str, object] = Field(default_factory=dict)


class RewriteOutput(StrictModel):
    proposal: Proposal
