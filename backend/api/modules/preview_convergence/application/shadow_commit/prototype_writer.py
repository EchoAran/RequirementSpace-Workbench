from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.model import (
    PreviewShadowDraftModel,
    PrototypePreviewModel,
)

from .common import _CommitIdMaps


def _build_prototype_id_maps(
    patch: dict,
    id_maps: _CommitIdMaps,
) -> tuple[dict[int, int], dict[int, int]]:
    temporary_id_to_negative: dict[str, int] = {}
    negative_id = -1001
    for actor_data in patch.get("actors_added", []):
        temporary_id_to_negative[actor_data["temp_id"]] = negative_id
        negative_id -= 1
    for feature_data in patch.get("features_added", []):
        temporary_id_to_negative[feature_data["temp_id"]] = negative_id
        negative_id -= 1

    actor_ids = {}
    feature_ids = {}
    for temporary_id, negative_id in temporary_id_to_negative.items():
        if temporary_id in id_maps.actors:
            actor_ids[negative_id] = id_maps.actors[temporary_id]
        if temporary_id in id_maps.features:
            feature_ids[negative_id] = id_maps.features[temporary_id]
    return actor_ids, feature_ids

def _map_prototype_pages(
    prototype_preview: dict,
    actor_ids: dict[int, int],
    feature_ids: dict[int, int],
) -> list[dict]:
    mapped_pages = []
    for page in prototype_preview.get("pages", []):
        role_id = page.get("roleId") or page.get("role_id")
        feature_id = page.get("featureId") or page.get("feature_id")
        mapped_role_id = (
            actor_ids.get(role_id, role_id)
            if isinstance(role_id, int) and role_id < 0
            else role_id
        )
        mapped_feature_id = (
            feature_ids.get(feature_id, feature_id)
            if isinstance(feature_id, int) and feature_id < 0
            else feature_id
        )
        mapped_pages.append(
            {
                "page_id": (
                    f"role-{mapped_role_id}-feature-{mapped_feature_id}"
                ),
                "role_id": mapped_role_id,
                "role_name": page.get("roleName") or page.get("role_name"),
                "feature_id": mapped_feature_id,
                "feature_name": (
                    page.get("featureName") or page.get("feature_name")
                ),
                "html": page.get("html"),
                "javascript": page.get("javascript"),
                "css": page.get("css"),
                "source": "committed_shadow_project",
                "status": "ready",
            }
        )
    return mapped_pages

async def _copy_prototype_preview(
    project_id: int,
    draft: PreviewShadowDraftModel,
    patch: dict,
    id_maps: _CommitIdMaps,
    prototype_generation_service,
    session: AsyncSession,
) -> None:
    prototype_preview = draft.prototype_preview_json
    if not prototype_preview:
        return
    actor_ids, feature_ids = _build_prototype_id_maps(patch, id_maps)
    mapped_pages = _map_prototype_pages(
        prototype_preview,
        actor_ids,
        feature_ids,
    )
    first_page = (
        mapped_pages[0]
        if mapped_pages
        else {
            "html": prototype_preview.get("html", ""),
            "javascript": prototype_preview.get("javascript", ""),
            "css": prototype_preview.get("css", ""),
        }
    )
    detail = (
        await prototype_generation_service._project_service.get_project_detail(
            project_id=project_id,
            session=session,
        )
    )
    session.add(
        PrototypePreviewModel(
            project_id=project_id,
            status="ready",
            source="committed_shadow_project",
            html=first_page["html"],
            javascript=first_page["javascript"],
            css=first_page["css"],
            pages=mapped_pages,
            input_snapshot=detail.model_dump(mode="json", by_alias=True),
        )
    )
    await session.flush()
