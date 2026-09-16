"""Request and response models. These generate the OpenAPI the frontend types from."""
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# The 21-character CIN structure, matching company.companies.cin_shape exactly.
# Validating here turns a typo into a 422 naming the format; without it the
# database CHECK fires and surfaces as an opaque 500.
# Format validation only - this makes no claim of registry verification.
CIN_PATTERN = r"^[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}$"
ISIN_PATTERN = r"^IN[A-Za-z0-9]{9}[0-9]$"


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
    """A company the user is putting on file.

    CIN is optional on purpose: a user testing a hypothetical company must not
    be blocked for want of one. A company without a CIN is marked as
    user-entered wherever it is shown.
    """
    name: str = Field(min_length=2, max_length=200)
    cin: Optional[str] = Field(default=None, pattern=CIN_PATTERN)
    incorporation_date: Optional[date] = None
    registered_office: Optional[str] = Field(default=None, max_length=500)
    company_type: Literal["PRIVATE", "PUBLIC", "SECTION_8", "NIDHI", "GOVERNMENT"] = "PRIVATE"
    listed_status: Literal["LISTED", "UNLISTED"] = "UNLISTED"
    exchanges: list[Literal["NSE", "BSE", "MSEI"]] = []
    ticker_symbol: Optional[str] = Field(default=None, max_length=20,
                                         pattern=r"^[A-Za-z0-9&.-]{1,20}$")
    isin: Optional[str] = Field(default=None, pattern=ISIN_PATTERN)
    is_sme: bool = False

    @model_validator(mode="after")
    def _listing_is_coherent(self):
        if self.listed_status == "LISTED" and not self.exchanges:
            raise ValueError("A listed company must name at least one stock exchange.")
        if self.listed_status == "UNLISTED" and (self.ticker_symbol or self.isin):
            raise ValueError("An unlisted company cannot have a ticker symbol or ISIN.")
        return self


class CapitalIn(BaseModel):
    authorised_capital: Decimal = Field(gt=0)
    issued_capital: Decimal = Field(ge=0)
    subscribed_capital: Optional[Decimal] = None
    paid_up_capital: Optional[Decimal] = None
    face_value: Decimal = Field(gt=0)
    shares_issued: Decimal = Field(ge=0)
    as_of_date: Optional[date] = None


class IssueHistoryIn(BaseModel):
    """A prior issue, recorded because earlier transactions condition eligibility.

    `client_ref` is minted by the browser per row so a retried submission after
    an ambiguous network failure cannot record the same issue twice.
    """
    client_ref: UUID
    issue_type: str
    security_type: str = "EQUITY_SHARES"
    status: Literal["PLANNED", "ANNOUNCED", "OPEN", "CLOSED",
                    "ALLOTTED", "WITHDRAWN"] = "ALLOTTED"
    announcement_date: Optional[date] = None
    board_resolution_date: Optional[date] = None
    shareholder_resolution_date: Optional[date] = None
    record_date: Optional[date] = None
    issue_open_date: Optional[date] = None
    issue_close_date: Optional[date] = None
    allotment_date: Optional[date] = None
    shares_offered: Optional[Decimal] = Field(default=None, gt=0)
    issue_price: Optional[Decimal] = Field(default=None, ge=0)
    # Not derived from the current face value: an issue predating a split would
    # be given a wrong premium. Supplied or left null.
    premium_per_share: Optional[Decimal] = None
    total_consideration: Optional[Decimal] = None
    rights_ratio_num: Optional[int] = Field(default=None, gt=0)
    rights_ratio_den: Optional[int] = Field(default=None, gt=0)


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
