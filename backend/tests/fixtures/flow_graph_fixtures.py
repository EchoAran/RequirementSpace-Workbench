import uuid
from dataclasses import dataclass, field
from typing import Any

_FIXTURE_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _fixture_uuid(name: str) -> str:
    """Generate a stable, deterministic RFC-4122 compliant UUID for fixtures."""
    return str(uuid.uuid5(_FIXTURE_NAMESPACE, f"flow_fixture_{name}"))


@dataclass(frozen=True)
class BusinessObjectFixtureData:
    """Fixture definition for a business object referenced by steps."""

    id: int
    logical_uuid: str
    name: str
    description: str


@dataclass(frozen=True)
class StepFixtureData:
    """Fixture definition for a single flow step with persistent identities."""

    id: int
    logical_uuid: str
    step_number: int
    name: str
    description: str
    step_type: str = "systemAction"
    input_object_ids: list[int] = field(default_factory=list)
    output_object_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class TransitionFixtureData:
    """Fixture definition for a transition with persistent identities."""

    id: int
    logical_uuid: str
    source_step_id: int
    target_step_id: int
    label: str
    condition_text: str
    is_default: bool = False
    semantic_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FlowGraphFixture:
    """Complete fixture definition for a flow graph topology."""

    id: int
    logical_uuid: str
    name: str
    description: str
    steps: list[StepFixtureData]
    transitions: list[TransitionFixtureData]
    business_objects: list[BusinessObjectFixtureData] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize fixture to a dictionary structure."""
        return {
            "id": self.id,
            "logical_uuid": self.logical_uuid,
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "id": s.id,
                    "logical_uuid": s.logical_uuid,
                    "step_number": s.step_number,
                    "name": s.name,
                    "description": s.description,
                    "step_type": s.step_type,
                    "input_object_ids": list(s.input_object_ids),
                    "output_object_ids": list(s.output_object_ids),
                }
                for s in self.steps
            ],
            "transitions": [
                {
                    "id": t.id,
                    "logical_uuid": t.logical_uuid,
                    "source_step_id": t.source_step_id,
                    "target_step_id": t.target_step_id,
                    "label": t.label,
                    "condition_text": t.condition_text,
                    "is_default": t.is_default,
                    "semantic_tags": list(t.semantic_tags),
                }
                for t in self.transitions
            ],
            "business_objects": [
                {
                    "id": b.id,
                    "logical_uuid": b.logical_uuid,
                    "name": b.name,
                    "description": b.description,
                }
                for b in self.business_objects
            ],
        }


def make_linear_flow_fixture() -> FlowGraphFixture:
    """1. Strictly sequential flow without branching."""
    return FlowGraphFixture(
        id=101,
        logical_uuid=_fixture_uuid("flow_linear_001"),
        name="Linear Order Submission",
        description="A simple 3-step sequence without branching.",
        steps=[
            StepFixtureData(1001, _fixture_uuid("step_lin_1"), 1, "Create Order", "User initiates order", "actorAction"),
            StepFixtureData(1002, _fixture_uuid("step_lin_2"), 2, "Calculate Total", "Calculate price and taxes", "systemAction"),
            StepFixtureData(1003, _fixture_uuid("step_lin_3"), 3, "Persist Order", "Save order record", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2001, _fixture_uuid("trans_lin_1"), 1001, 1002, "Proceed", "Order valid", is_default=True),
            TransitionFixtureData(2002, _fixture_uuid("trans_lin_2"), 1002, 1003, "Complete", "Calculation done", is_default=True),
        ],
    )


def make_branch_and_join_fixture() -> FlowGraphFixture:
    """2. Single judgment step with two branches reconverging to a join step."""
    return FlowGraphFixture(
        id=102,
        logical_uuid=_fixture_uuid("flow_branch_join_002"),
        name="Payment Assessment with Join",
        description="Single judgment branching into auto capture and manual review, then joining.",
        steps=[
            StepFixtureData(1011, _fixture_uuid("step_bj_1"), 1, "Submit Payment", "User submits payment", "actorAction"),
            StepFixtureData(1012, _fixture_uuid("step_bj_2"), 2, "Risk Judgment", "Evaluate risk level", "judgment"),
            StepFixtureData(1013, _fixture_uuid("step_bj_3"), 3, "Auto Capture", "Instant settlement", "systemAction"),
            StepFixtureData(1014, _fixture_uuid("step_bj_4"), 4, "Manual Review", "Officer inspects details", "actorAction"),
            StepFixtureData(1015, _fixture_uuid("step_bj_5"), 5, "Send Notification", "Notify customer of status", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2011, _fixture_uuid("trans_bj_1"), 1011, 1012, "Evaluate", "Form submitted", is_default=True),
            TransitionFixtureData(2012, _fixture_uuid("trans_bj_2"), 1012, 1013, "Low Risk", "Risk score <= 30", is_default=True),
            TransitionFixtureData(2013, _fixture_uuid("trans_bj_3"), 1012, 1014, "High Risk", "Risk score > 30", is_default=False, semantic_tags=["manual_review"]),
            TransitionFixtureData(2014, _fixture_uuid("trans_bj_4"), 1013, 1015, "Captured", "Payment succeeded", is_default=True),
            TransitionFixtureData(2015, _fixture_uuid("trans_bj_5"), 1014, 1015, "Approved", "Officer approved", is_default=False),
        ],
    )


def make_multi_exit_non_judgment_fixture() -> FlowGraphFixture:
    """3. Non-judgment step with multiple exits (e.g. actor action cancellation or submission)."""
    return FlowGraphFixture(
        id=103,
        logical_uuid=_fixture_uuid("flow_non_judgment_multi_003"),
        name="User Form Confirmation Multiple Exits",
        description="Actor action step with submit and cancel outlets.",
        steps=[
            StepFixtureData(1021, _fixture_uuid("step_nj_1"), 1, "Fill Form", "User inputs details", "actorAction"),
            StepFixtureData(1022, _fixture_uuid("step_nj_2"), 2, "Review Details", "User reviews summary on dialog", "actorAction"),
            StepFixtureData(1023, _fixture_uuid("step_nj_3"), 3, "Process Submission", "Backend accepts form", "systemAction"),
            StepFixtureData(1024, _fixture_uuid("step_nj_4"), 4, "Discard Draft", "Backend discards input", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2021, _fixture_uuid("trans_nj_1"), 1021, 1022, "Review", "Input complete", is_default=True),
            TransitionFixtureData(2022, _fixture_uuid("trans_nj_2"), 1022, 1023, "Confirm", "User clicks confirm", is_default=True),
            TransitionFixtureData(2023, _fixture_uuid("trans_nj_3"), 1022, 1024, "Cancel", "User clicks cancel", is_default=False, semantic_tags=["user_cancellation"]),
        ],
    )


def make_branch_without_join_fixture() -> FlowGraphFixture:
    """4. Flow branching into separate terminal steps without join."""
    return FlowGraphFixture(
        id=104,
        logical_uuid=_fixture_uuid("flow_branch_no_join_004"),
        name="Account Verification Distinct Terminals",
        description="Branching leads to separate terminal outcomes without merging.",
        steps=[
            StepFixtureData(1031, _fixture_uuid("step_bnj_1"), 1, "Verify Identity", "Check identity documents", "judgment"),
            StepFixtureData(1032, _fixture_uuid("step_bnj_2"), 2, "Activate Account", "Grant full platform access", "systemAction"),
            StepFixtureData(1033, _fixture_uuid("step_bnj_3"), 3, "Reject Application", "Record reason and close ticket", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2031, _fixture_uuid("trans_bnj_1"), 1031, 1032, "Pass", "Identity verified", is_default=True),
            TransitionFixtureData(2032, _fixture_uuid("trans_bnj_2"), 1031, 1033, "Fail", "Identity forged or expired", is_default=False, semantic_tags=["terminal_rejection"]),
        ],
    )


def make_cycle_retry_fixture() -> FlowGraphFixture:
    """5. Flow with a backward edge representing a retry loop."""
    return FlowGraphFixture(
        id=105,
        logical_uuid=_fixture_uuid("flow_cycle_retry_005"),
        name="API Invocation with Retry Loop",
        description="Step loops back to previous invocation step on network failure.",
        steps=[
            StepFixtureData(1041, _fixture_uuid("step_cr_1"), 1, "Prepare Payload", "Assemble API request", "systemAction"),
            StepFixtureData(1042, _fixture_uuid("step_cr_2"), 2, "Invoke Endpoint", "Send HTTP POST", "systemAction"),
            StepFixtureData(1043, _fixture_uuid("step_cr_3"), 3, "Check Response", "Evaluate status code", "judgment"),
            StepFixtureData(1044, _fixture_uuid("step_cr_4"), 4, "Store Result", "Persist response data", "systemAction"),
            StepFixtureData(1045, _fixture_uuid("step_cr_5"), 5, "Fallback Degradation", "Use cached data", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2041, _fixture_uuid("trans_cr_1"), 1041, 1042, "Send", "Payload ready", is_default=True),
            TransitionFixtureData(2042, _fixture_uuid("trans_cr_2"), 1042, 1043, "Evaluate", "HTTP response returned", is_default=True),
            TransitionFixtureData(2043, _fixture_uuid("trans_cr_3"), 1043, 1044, "Success", "HTTP 200", is_default=True),
            TransitionFixtureData(2044, _fixture_uuid("trans_cr_4"), 1043, 1042, "Retry", "HTTP 5xx and count < 3", is_default=False, semantic_tags=["retry", "cycle"]),
            TransitionFixtureData(2045, _fixture_uuid("trans_cr_5"), 1043, 1045, "Exhausted", "count >= 3", is_default=False, semantic_tags=["fallback"]),
        ],
    )


def make_pure_cycle_fixture() -> FlowGraphFixture:
    """6. Entire flow is a cycle with no zero-in-degree entry step."""
    return FlowGraphFixture(
        id=106,
        logical_uuid=_fixture_uuid("flow_pure_cycle_006"),
        name="Periodic Heartbeat Ring",
        description="Continuous polling loop where every step has incoming edges.",
        steps=[
            StepFixtureData(1051, _fixture_uuid("step_pc_1"), 1, "Poll Health Status", "Ping agent endpoint", "systemAction"),
            StepFixtureData(1052, _fixture_uuid("step_pc_2"), 2, "Record Metric", "Store latency telemetry", "systemAction"),
            StepFixtureData(1053, _fixture_uuid("step_pc_3"), 3, "Wait Interval", "Sleep for 10 seconds", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2051, _fixture_uuid("trans_pc_1"), 1051, 1052, "Metric Ready", "Ping answered", is_default=True),
            TransitionFixtureData(2052, _fixture_uuid("trans_pc_2"), 1052, 1053, "Recorded", "Metric persisted", is_default=True),
            TransitionFixtureData(2053, _fixture_uuid("trans_pc_3"), 1053, 1051, "Timer Fired", "Interval elapsed", is_default=True, semantic_tags=["ring_cycle"]),
        ],
    )


def make_unreachable_step_fixture() -> FlowGraphFixture:
    """7. Flow containing an orphaned / unreachable step with in-degree 0 not being start."""
    return FlowGraphFixture(
        id=107,
        logical_uuid=_fixture_uuid("flow_unreachable_007"),
        name="Flow with Disconnected Step",
        description="Contains a step not reachable from any initial sequence.",
        steps=[
            StepFixtureData(1061, _fixture_uuid("step_ur_1"), 1, "Start Process", "Initiate workflow", "actorAction"),
            StepFixtureData(1062, _fixture_uuid("step_ur_2"), 2, "Finish Process", "Terminate workflow", "systemAction"),
            StepFixtureData(1063, _fixture_uuid("step_ur_3"), 3, "Dangling Cleanup", "Unreachable legacy cleanup step", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2061, _fixture_uuid("trans_ur_1"), 1061, 1062, "Proceed", "Step 1 complete", is_default=True),
        ],
    )


def make_multi_flow_shared_object_fixture() -> tuple[FlowGraphFixture, FlowGraphFixture, BusinessObjectFixtureData]:
    """8. Single business object shared across two distinct flows."""
    shared_object = BusinessObjectFixtureData(
        id=5001,
        logical_uuid=_fixture_uuid("bo_shared_order_5001"),
        name="OrderEntity",
        description="Shared core order business object.",
    )

    flow_a = FlowGraphFixture(
        id=108,
        logical_uuid=_fixture_uuid("flow_shared_obj_a_008"),
        name="Order Creation Flow",
        description="Creates OrderEntity.",
        steps=[
            StepFixtureData(1071, _fixture_uuid("step_so_1"), 1, "Enter Order", "Customer fills order info", "actorAction"),
            StepFixtureData(
                1072, _fixture_uuid("step_so_2"), 2, "Instantiate Order", "Create order record", "systemAction",
                output_object_ids=[shared_object.id]
            ),
        ],
        transitions=[
            TransitionFixtureData(2071, _fixture_uuid("trans_so_1"), 1071, 1072, "Submit", "Input valid", is_default=True),
        ],
        business_objects=[shared_object],
    )

    flow_b = FlowGraphFixture(
        id=109,
        logical_uuid=_fixture_uuid("flow_shared_obj_b_009"),
        name="Order Fulfillment Flow",
        description="Reads OrderEntity.",
        steps=[
            StepFixtureData(
                1081, _fixture_uuid("step_so_3"), 1, "Load Order", "Warehouse system loads order", "systemAction",
                input_object_ids=[shared_object.id]
            ),
            StepFixtureData(1082, _fixture_uuid("step_so_4"), 2, "Dispatch Shipment", "Carrier dispatches package", "systemAction"),
        ],
        transitions=[
            TransitionFixtureData(2081, _fixture_uuid("trans_so_2"), 1081, 1082, "Ship", "Warehouse packed", is_default=True),
        ],
        business_objects=[shared_object],
    )

    return flow_a, flow_b, shared_object
