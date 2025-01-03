# AUTOGENERATED FROM 'common/queries/templates/template_create.edgeql' WITH:
#     $ edgedb-py --tls-security=insecure -P 5656 -d precepto --dir ./common/queries


from __future__ import annotations
import dataclasses
import edgedb
import uuid


class NoPydanticValidation:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        # Pydantic 2.x
        from pydantic_core.core_schema import any_schema
        return any_schema()

    @classmethod
    def __get_validators__(cls):
        # Pydantic 1.x
        from pydantic.dataclasses import dataclass as pydantic_dataclass
        _ = pydantic_dataclass(cls)
        cls.__pydantic_model__.__get_validators__ = lambda: []
        return []


@dataclasses.dataclass
class TemplateCreateResult(NoPydanticValidation):
    id: uuid.UUID


async def template_create(
    executor: edgedb.AsyncIOExecutor,
    *,
    name: str,
    description: str | None = None,
    template: str,
    is_public: bool | None = None,
    image_url: str | None = None,
    user_id: uuid.UUID,
) -> TemplateCreateResult:
    return await executor.query_single(
        """\
        # Create a new template
        INSERT Template {
            name := <str>$name,
            description := <optional str>$description,
            template := <str>$template,
            is_public := <optional bool>$is_public,
            image_url := <optional str>$image_url,
            created_by := (select User filter .id = <uuid>$user_id)
        };\
        """,
        name=name,
        description=description,
        template=template,
        is_public=is_public,
        image_url=image_url,
        user_id=user_id,
    )
