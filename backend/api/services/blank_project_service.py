from backend.core.generators.blank_project_generator import (
    BlankProjectGenerator,
    BlankProjectGeneratorInput,
)


class BlankProjectService:
    def __init__(self):
        self._blank_project_generator = BlankProjectGenerator()

    async def create_project(
        self,
        user_requirements: str,
        project_name: str | None,
        project_description: str | None,
        owner_user_id: int,
        session,
    ) -> dict:
        from backend.database.model import ProjectModel

        normalized_name = self._normalize_optional_text(project_name)
        normalized_description = self._normalize_optional_text(
            project_description
        )

        if normalized_name is None or normalized_description is None:
            raw = await self._blank_project_generator.generate(
                BlankProjectGeneratorInput(
                    user_requirements=user_requirements,
                )
            )

            generated_name = raw.get("project_name")
            generated_description = raw.get("project_description")

            if not generated_name or not generated_description:
                raise ValueError("invalid_project_payload")

            normalized_name = normalized_name or generated_name
            normalized_description = (
                normalized_description or generated_description
            )

        project = ProjectModel(
            name=normalized_name,
            description=normalized_description,
            user_requirements=user_requirements,
            owner_user_id=owner_user_id,
        )

        session.add(project)
        await session.flush()
        # Commit before returning so the follow-up GET /projects/{id}
        # in the frontend can always observe the newly created project.
        await session.commit()
        await session.refresh(project)

        return {
            "project_id": project.public_id,
            "project_name": project.name,
            "project_description": project.description,
            "message": "project_created",
        }

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None
