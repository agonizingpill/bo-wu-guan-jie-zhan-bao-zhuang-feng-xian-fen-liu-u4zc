from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator


class Role(StrEnum):
    OPERATOR = 'operator'
    SUPERVISOR = 'supervisor'
    VIEWER = 'viewer'


class LoanStatus(StrEnum):
    REGISTERED = 'registered'
    PACKING = 'packing'
    TRIAGE_PENDING = 'triage_pending'
    READY = 'ready'
    REVIEW_REQUIRED = 'review_required'
    SAMPLING = 'sampling'
    HOLD = 'hold'
    DISPATCHED = 'dispatched'


class ReviewStatus(StrEnum):
    AWAITING_WITNESS = 'awaiting_witness'
    AWAITING_SUPERVISOR = 'awaiting_supervisor'
    SAMPLING = 'sampling'
    HELD = 'held'
    CLEARED = 'cleared'


class Material(StrEnum):
    PORCELAIN = 'porcelain'
    PAPER = 'paper'
    BRONZE = 'bronze'


class Packing(StrEnum):
    FOAM = 'foam'
    SUSPENSION = 'suspension'
    DOUBLE_WALL = 'double_wall'


class RouteType(StrEnum):
    DIRECT = 'direct'
    TRANSFER = 'transfer'
    MOUNTAIN = 'mountain'


Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=96)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r'^[A-Za-z0-9][A-Za-z0-9-]{2,31}$')]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=600)]


class Login(BaseModel):
    username: Label
    password: str = Field(min_length=1, max_length=200)


class StaffMember(BaseModel):
    username: str
    display_name: str
    role: Role


class LoanIntake(BaseModel):
    accession: Code
    object_name: Label
    lender: Label
    gallery: Label
    must_arrive: AwareDatetime


class CrateInspection(BaseModel):
    crate_code: Code
    seal_code: Code | None = None
    material: Material
    packing: Packing
    route_type: RouteType
    max_rh: int = Field(ge=0, le=100)
    transfers: int = Field(ge=0, le=8)


class Interval(BaseModel):
    begins_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode='after')
    def validate_interval(self):
        if self.ends_at <= self.begins_at:
            raise ValueError('窗口结束时间必须晚于开始时间')
        return self


class TransitReservation(Interval):
    vehicle: Label


class GallerySetup(Interval):
    gallery: Label
    label: Label


class Witness(BaseModel):
    note: Reason


class ReviewDecision(BaseModel):
    verdict: Literal['downgrade', 'hold']
    reason: Reason


class SampleObservation(BaseModel):
    seal_code: Code


class ReopenReview(BaseModel):
    reason: Reason
