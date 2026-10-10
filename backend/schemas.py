from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal['C01','C02','C03','C04','C05','C06','C07','C08','C09','C10']
Scope = Literal['fixed','variable','hypothetical']
Model = Literal['F70','G60','G70']
Origin = Literal['observed','synthetic','unknown']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)

class Content(Strict):
    title: str = Field(min_length=1,max_length=200)
    statement: str = Field(min_length=1,max_length=5000)
    baseline_value: str | None = Field(default=None,max_length=1000)
    target_value: Decimal | None = None
    unit: str | None = Field(default=None,max_length=100)
    conditions: str | None = Field(default=None,max_length=2000)
    acceptance_test: str | None = Field(default=None,max_length=2000)
    owner: str | None = Field(default=None,max_length=200)

    @field_validator('target_value')
    @classmethod
    def finite(cls,value):
        if value is not None and not value.is_finite():
            raise ValueError('Target must be finite')
        return value

    def specification_status(self):
        return 'specified' if self.target_value is not None and all([self.unit,self.conditions,self.acceptance_test,self.owner]) else 'needs_specification'

class Draft(Content):
    model_code: Model
    market_code: str | None = Field(default=None,pattern=r'^[A-Z]{2}$')
    category_id: Category
    scope_layer: Scope = 'fixed'
    evidence_ids: list[str] = Field(min_length=1,max_length=50)
    rationale: str = Field(min_length=1,max_length=2000)

    @field_validator('evidence_ids')
    @classmethod
    def ids(cls,values):
        if any(not x.isdigit() or int(x)<1 for x in values) or len(set(values)) != len(values):
            raise ValueError('Evidence IDs must be unique positive opaque strings')
        return values

class Action(Strict):
    action: Literal['approve','edit','reject','postpone']
    expected_revision: int = Field(ge=1)
    rationale: str = Field(min_length=1,max_length=2000)
    content: Content | None = None
    review_date: date | None = None
    unscheduled: bool = False

    @model_validator(mode='after')
    def action_fields(self):
        if (self.action=='edit') != (self.content is not None):
            raise ValueError('Only edit requires complete content')
        if self.action=='postpone':
            if (self.review_date is not None)==self.unscheduled:
                raise ValueError('Postpone requires a date or explicit unscheduled state')
            if self.review_date and self.review_date < date.today():
                raise ValueError('Review date must not be in the past')
        elif self.review_date or self.unscheduled:
            raise ValueError('Review scheduling applies only to postpone')
        return self

class Filters(Strict):
    model_code: Model = 'G60'
    market_code: str | None = Field(default=None,pattern=r'^[A-Z]{2}$')
    version_id: str | None = Field(default=None,pattern=r'^[1-9][0-9]*$')
    category_id: Category | None = None
    scope_layer: Scope | None = None
    data_origin: Origin | None = None
    review_status: Literal['unreviewed','reviewed','rejected'] | None = None
    evidence_kind: Literal['customer_statement','published_specification','derived_assessment'] | None = None
    priority: Literal['unscored'] | None = None
    q: str = Field(default='',max_length=200)
    sort: Literal['id','title'] = 'id'
    direction: Literal['asc','desc'] = 'asc'
    page: int = Field(default=1,ge=1,le=100000)
    page_size: int = Field(default=20,ge=1,le=100)
    unknown_market_only: bool = False

    @model_validator(mode='after')
    def market_choice(self):
        if self.unknown_market_only and self.market_code:
            raise ValueError('Unknown market filter cannot be combined with a country')
        return self

class Page(Strict):
    items: list[dict]
    total: int
    page: int
    page_size: int
    effective_filters: dict
