from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ApiMeta(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page: int = 1
    limit: int = 20
    total: int = 0
    total_pages: int | None = None
    cursor: str | None = None
    next_cursor: str | None = None


class ListQueryParams(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    q: str | None = None
    page: int = 1
    limit: int = 20
    sort: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
