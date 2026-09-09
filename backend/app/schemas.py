"""Request and response models. These generate the OpenAPI the frontend types from."""
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------- company
class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    cin: Optional[str] = None
    incorporation_date: Optional[date] = None
    company_type: Literal["PRIVATE", "PUBLIC", "SECTION_8", "NIDHI", "GOVERNMENT"] = "PRIVATE"
    listed_status: Literal["LISTED", "UNLISTED"] = "UNLISTED"
    exchanges: list[Literal["NSE", "BSE", "MSEI"]] = []
    is_sme: bool = False


class CapitalIn(BaseModel):
    authorised_capital: Decimal = Field(gt=0)
    issued_capital: Decimal = Field(ge=0)
    subscribed_capital: Optional[Decimal] = None
    paid_up_capital: Optional[Decimal] = None
    face_value: Decimal = Field(gt=0)
    shares_issued: Decimal = Field(ge=0)
    as_of_date: Optional[date] = None


class HoldingIn(BaseModel):
    name: str
    shares_held: Decimal = Field(ge=0)
    category: Optional[str] = None
    is_promoter: bool = False
    shares_allotted: Decimal = 0


# ------------------------------------------------------------------ issue
class ProposedIssue(BaseModel):
    """The transaction under consideration.

    `extra` carries the route-specific answers declared by the route manifest,
    so adding a question to a route needs no schema change here.
    """
    issue_type: str
    security_type: str = "EQUITY_SHARES"
    shares_proposed: Optional[Decimal] = None
    issue_price: Optional[Decimal] = None
    face_value: Optional[Decimal] = None
    purpose: Optional[str] = None
    board_resolution_date: Optional[date] = None
    allotment_date: Optional[date] = None
    extra: dict[str, Any] = {}


class AssessmentRequest(BaseModel):
    company_id: UUID
    transaction_date: date
    issue: ProposedIssue
    holdings: Optional[list[HoldingIn]] = None
    scenario_name: Optional[str] = None
    persist: bool = True


class CalculationPreviewRequest(BaseModel):
    capital: CapitalIn
    issue: ProposedIssue
    holdings: Optional[list[HoldingIn]] = None


class RouteGuidanceRequest(BaseModel):
    company_id: Optional[UUID] = None
    listed_status: Literal["LISTED", "UNLISTED", "UNKNOWN"] = "UNKNOWN"
    offered_to_existing_shareholders: Optional[bool] = None
    allottee_count: Optional[int] = None


# ------------------------------------------------------------------ admin
class ReviewDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "NEEDS_INFO"]
    notes: Optional[str] = None
