"""Company records within the signed-in organisation."""
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...db import fetch_all, fetch_one, tx
from ...deps import (ROLE_RANK, Principal, current_principal, require_company_access,
                     require_role)
from ...domain import route_manifests
from ...schemas import CapitalIn, CompanyCreate, HoldingIn, IssueHistoryIn

router = APIRouter(prefix="/companies", tags=["companies"])


def company_facts(conn, company_id: str) -> dict:
    """Assemble a company's current facts for the engines."""
    co = fetch_one(conn, "SELECT * FROM company.companies WHERE company_id=%s", (str(company_id),))
    if co is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found.")
    cls = fetch_one(conn, """
        SELECT * FROM company.company_classifications
        WHERE company_id=%s ORDER BY effective_from DESC LIMIT 1""", (str(company_id),))
    cap = fetch_one(conn, """
        SELECT * FROM company.capital_snapshots
        WHERE company_id=%s ORDER BY as_of_date DESC LIMIT 1""", (str(company_id),))
    holdings = fetch_all(conn, """
        SELECT s.name, s.category, s.is_promoter, h.shares_held
        FROM company.holdings h JOIN company.shareholders s USING (shareholder_id)
        WHERE s.company_id=%s AND h.as_of_date =
              (SELECT max(as_of_date) FROM company.holdings h2 WHERE h2.shareholder_id=h.shareholder_id)
        ORDER BY h.shares_held DESC""", (str(company_id),))
    issues = fetch_all(conn, """
        SELECT issue_id, issue_type, security_type, status, announcement_date,
               board_resolution_date, shareholder_resolution_date, record_date,
               issue_open_date, issue_close_date, allotment_date, shares_offered,
               issue_price, premium_per_share, total_consideration,
               rights_ratio_num, rights_ratio_den
        FROM company.issues WHERE company_id=%s
        ORDER BY coalesce(allotment_date, issue_close_date, board_resolution_date) DESC NULLS LAST""",
        (str(company_id),))
    return {"company": co, "classification": cls, "capital": cap,
            "holdings": holdings, "issues": issues}


def _require_finance_once_relied_upon(conn, p: Principal, company_id: str, what: str) -> None:
    """Let any member enter a company's financials until they have been used.

    The role bar exists to protect figures that have been relied upon, not to
    stop a record being created. A company secretary putting a client's capital
    on file for the first time is doing data entry; the demo company secretary
    is a COMPANY_USER, so requiring Finance for that first write would strand
    the persona this whole flow is built for with a company they cannot assess.

    The line is drawn at the first assessment rather than at the first write.
    Before then the figures are a draft the same user is still correcting - a
    typo in a cap table they entered a minute ago must be fixable. Once an
    assessment has cited them they are part of an audit trail, and changing
    them is a financial amendment that belongs to Finance.
    """
    if ROLE_RANK.get(p.role, 0) >= ROLE_RANK["FINANCE_USER"]:
        return
    relied_on = fetch_one(conn, """
        SELECT 1 FROM assess.scenarios WHERE company_id=%s LIMIT 1""", (company_id,))
    if relied_on is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{what} has already been used in an assessment for this company. "
            "Only a Finance User or an Administrator can change it now.")


@router.get("")
def list_companies(q: str | None = Query(default=None, max_length=120),
                   limit: int = Query(default=25, ge=1, le=100),
                   offset: int = Query(default=0, ge=0),
                   p: Principal = Depends(current_principal)):
    """Companies in the organisation, searchable by name, CIN, ticker or ISIN.

    The filter and the page are applied to company.companies first, and only
    the resulting page is joined to its classification and capital snapshot.
    Joining first would run two lateral subqueries for every company in the
    organisation to return twenty-five rows.
    """
    term = f"%{q.strip()}%" if q and q.strip() else None
    with tx(p.org_id) as conn:
        total = fetch_one(conn, """
            SELECT count(*) AS n FROM company.companies c
            WHERE %(t)s::text IS NULL OR c.name ILIKE %(t)s::text OR c.cin ILIKE %(t)s::text
               OR EXISTS (SELECT 1 FROM company.company_classifications x
                          WHERE x.company_id = c.company_id
                            AND (x.ticker_symbol ILIKE %(t)s::text OR x.isin ILIKE %(t)s::text))""",
            {"t": term})["n"]
        rows = fetch_all(conn, """
            WITH page AS (
              SELECT c.* FROM company.companies c
              WHERE %(t)s::text IS NULL OR c.name ILIKE %(t)s::text OR c.cin ILIKE %(t)s::text
                 OR EXISTS (SELECT 1 FROM company.company_classifications x
                            WHERE x.company_id = c.company_id
                              AND (x.ticker_symbol ILIKE %(t)s::text OR x.isin ILIKE %(t)s::text))
              ORDER BY c.name LIMIT %(limit)s OFFSET %(offset)s)
            SELECT c.company_id, c.name, c.cin, c.incorporation_date, c.registered_office,
                   cc.company_type, cc.listed_status, cc.exchanges, cc.is_sme,
                   cc.ticker_symbol, cc.isin,
                   cs.authorised_capital, cs.issued_capital, cs.subscribed_capital,
                   cs.paid_up_capital, cs.face_value, cs.shares_issued,
                   cs.as_of_date AS capital_as_of,
                   (SELECT count(*) FROM company.shareholders sh
                     WHERE sh.company_id = c.company_id) AS holder_count,
                   (SELECT count(*) FROM company.issues i
                     WHERE i.company_id = c.company_id) AS issue_count
            FROM page c
            LEFT JOIN LATERAL (
              SELECT * FROM company.company_classifications x
              WHERE x.company_id=c.company_id ORDER BY effective_from DESC LIMIT 1) cc ON true
            LEFT JOIN LATERAL (
              SELECT * FROM company.capital_snapshots x
              WHERE x.company_id=c.company_id ORDER BY as_of_date DESC LIMIT 1) cs ON true
            ORDER BY c.name""",
            {"t": term, "limit": limit, "offset": offset})
    return {"companies": rows, "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyCreate,
                   p: Principal = Depends(require_role("COMPANY_USER"))):
    warnings: list[str] = []
    with tx(p.org_id) as conn:
        # A duplicate CIN warns rather than blocks: a company may be
        # re-registered, and a user may legitimately want a second scenario
        # against the same client. The per-org unique index is the backstop.
        if body.cin:
            dup = fetch_one(conn, "SELECT name FROM company.companies WHERE cin=%s",
                            (body.cin,))
            if dup:
                warnings.append(
                    f"{dup['name']} is already on file with this CIN. "
                    "Check you are not creating a duplicate.")
        row = fetch_one(conn, """
            INSERT INTO company.companies
              (org_id, name, cin, incorporation_date, registered_office)
            VALUES (%s,%s,%s,%s,%s) RETURNING company_id, name, cin""",
            (p.org_id, body.name, body.cin, body.incorporation_date, body.registered_office))
        conn.execute("""
            INSERT INTO company.company_classifications
              (org_id, company_id, company_type, listed_status, exchanges, is_sme,
               ticker_symbol, isin, effective_from)
            VALUES (%s,%s,%s,%s,%s::legal.exchange[],%s,%s,%s,%s)""",
            (p.org_id, row["company_id"], body.company_type, body.listed_status,
             body.exchanges, body.is_sme, body.ticker_symbol, body.isin,
             body.incorporation_date or date.today()))
    # Stated, not implied: a CIN is format-checked and never registry-verified.
    return {**row, "warnings": warnings}


@router.get("/{company_id}")
def get_company(company_id: UUID, p: Principal = Depends(current_principal)):
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        return company_facts(conn, str(company_id))


@router.put("/{company_id}/capital")
def set_capital(company_id: UUID, body: CapitalIn,
                p: Principal = Depends(require_role("COMPANY_USER"))):
    subscribed = body.subscribed_capital if body.subscribed_capital is not None else body.issued_capital
    paid_up = body.paid_up_capital if body.paid_up_capital is not None else subscribed
    # Surfaced before the database rejects it, so the user sees which two
    # figures conflict rather than a constraint name.
    if body.issued_capital > body.authorised_capital:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Issued capital cannot exceed authorised capital.")
    if paid_up > subscribed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Paid-up capital cannot exceed subscribed capital.")
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        _require_finance_once_relied_upon(conn, p, str(company_id), "The capital structure")
        sc = fetch_one(conn, """SELECT share_class_id FROM company.share_classes
                                WHERE company_id=%s ORDER BY name LIMIT 1""", (str(company_id),))
        if sc is None:
            sc = fetch_one(conn, """
                INSERT INTO company.share_classes
                  (org_id, company_id, name, security_type, face_value)
                VALUES (%s,%s,'Equity','EQUITY_SHARES',%s) RETURNING share_class_id""",
                (p.org_id, str(company_id), body.face_value))
        as_of = body.as_of_date or date.today()
        conn.execute("""
            INSERT INTO company.capital_snapshots
              (org_id, company_id, share_class_id, as_of_date, authorised_capital,
               issued_capital, subscribed_capital, paid_up_capital, face_value, shares_issued)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (company_id, share_class_id, as_of_date) DO UPDATE SET
              authorised_capital=EXCLUDED.authorised_capital,
              issued_capital=EXCLUDED.issued_capital,
              subscribed_capital=EXCLUDED.subscribed_capital,
              paid_up_capital=EXCLUDED.paid_up_capital,
              face_value=EXCLUDED.face_value, shares_issued=EXCLUDED.shares_issued""",
            (p.org_id, str(company_id), sc["share_class_id"], as_of, body.authorised_capital,
             body.issued_capital, subscribed, paid_up, body.face_value, body.shares_issued))
    return {"status": "saved", "as_of_date": str(as_of)}


@router.put("/{company_id}/holdings")
def set_holdings(company_id: UUID, holdings: list[HoldingIn],
                 p: Principal = Depends(require_role("COMPANY_USER"))):
    """Record the cap table as at today.

    This used to DELETE every shareholder and re-insert, cascading into
    company.holdings - a table keyed by as_of_date precisely so it can hold a
    time series, and carrying locked_in_shares and lock_in_until that this
    form never collects. Almost nothing called it before; now every run of the
    wizard does, so it writes a new dated row per holder and leaves earlier
    dates, lock-in and the shareholder's other attributes untouched.
    """
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        _require_finance_once_relied_upon(conn, p, str(company_id), "The cap table")
        sc = fetch_one(conn, """SELECT share_class_id FROM company.share_classes
                                WHERE company_id=%s ORDER BY name LIMIT 1""", (str(company_id),))
        if sc is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Record the capital structure before the cap table.")
        as_of = date.today()
        for h in holdings:
            # Matched by name: shareholders carries no unique key, and a holder
            # re-entered with a corrected share count is the same holder.
            row = fetch_one(conn, """
                SELECT shareholder_id FROM company.shareholders
                WHERE company_id=%s AND lower(name)=lower(%s) LIMIT 1""",
                (str(company_id), h.name))
            if row is None:
                row = fetch_one(conn, """
                    INSERT INTO company.shareholders
                      (org_id, company_id, name, category, is_promoter)
                    VALUES (%s,%s,%s,%s,%s) RETURNING shareholder_id""",
                    (p.org_id, str(company_id), h.name, h.category or "PUBLIC", h.is_promoter))
            else:
                conn.execute("""
                    UPDATE company.shareholders SET category=%s, is_promoter=%s
                    WHERE shareholder_id=%s""",
                    (h.category or "PUBLIC", h.is_promoter, row["shareholder_id"]))
            conn.execute("""
                INSERT INTO company.holdings
                  (org_id, shareholder_id, share_class_id, as_of_date, shares_held)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (shareholder_id, share_class_id, as_of_date)
                DO UPDATE SET shares_held = EXCLUDED.shares_held""",
                (p.org_id, row["shareholder_id"], sc["share_class_id"], as_of, h.shares_held))
        # A holder left out of the submission has left the register today; that
        # is recorded as a nil holding rather than by deleting their history.
        names = [h.name.lower() for h in holdings]
        conn.execute("""
            INSERT INTO company.holdings
              (org_id, shareholder_id, share_class_id, as_of_date, shares_held)
            SELECT %s, sh.shareholder_id, %s, %s, 0
            FROM company.shareholders sh
            WHERE sh.company_id=%s AND NOT (lower(sh.name) = ANY(%s))
            ON CONFLICT (shareholder_id, share_class_id, as_of_date) DO NOTHING""",
            (p.org_id, sc["share_class_id"], as_of, str(company_id), names))
    return {"status": "saved", "holders": len(holdings), "as_of_date": str(as_of)}


@router.get("/{company_id}/issues")
def list_issues(company_id: UUID, p: Principal = Depends(current_principal)):
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        return {"issues": company_facts(conn, str(company_id))["issues"]}


@router.post("/{company_id}/issues", status_code=status.HTTP_201_CREATED)
def record_issues(company_id: UUID, issues: list[IssueHistoryIn],
                  p: Principal = Depends(require_role("COMPANY_USER"))):
    """Append prior issues to a company's history.

    Append rather than replace: assess.scenarios.issue_id references
    company.issues ON DELETE SET NULL, so replace-all semantics would silently
    detach historical assessments from the issue they were run against.
    client_ref makes a retry after an ambiguous failure a no-op.
    """
    for i in issues:
        # Checked here so the user is told which two dates conflict, rather
        # than meeting the issue_dates_sane constraint name.
        if i.issue_open_date and i.issue_close_date and i.issue_close_date < i.issue_open_date:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "An issue cannot close before it opens.")
        if i.issue_close_date and i.allotment_date and i.allotment_date < i.issue_close_date:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Allotment cannot be dated before the issue closes.")
        if i.issue_type not in route_manifests.ALL_ROUTES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"Unknown issue route: {i.issue_type}")
    recorded = 0
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        for i in issues:
            total = i.total_consideration
            if total is None and i.shares_offered is not None and i.issue_price is not None:
                total = i.shares_offered * i.issue_price
            row = fetch_one(conn, """
                INSERT INTO company.issues
                  (org_id, company_id, client_ref, issue_type, security_type, status,
                   announcement_date, board_resolution_date, shareholder_resolution_date,
                   record_date, issue_open_date, issue_close_date, allotment_date,
                   shares_offered, issue_price, premium_per_share, total_consideration,
                   rights_ratio_num, rights_ratio_den)
                VALUES (%s,%s,%s,%s::legal.issue_type,%s::legal.security_type,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                -- The index is partial, so its predicate must be restated
                -- here for Postgres to match it as the arbiter.
                ON CONFLICT (company_id, client_ref) WHERE client_ref IS NOT NULL
                DO NOTHING
                RETURNING issue_id""",
                (p.org_id, str(company_id), str(i.client_ref), i.issue_type, i.security_type,
                 i.status, i.announcement_date, i.board_resolution_date,
                 i.shareholder_resolution_date, i.record_date, i.issue_open_date,
                 i.issue_close_date, i.allotment_date, i.shares_offered, i.issue_price,
                 i.premium_per_share, total, i.rights_ratio_num, i.rights_ratio_den))
            if row is not None:
                recorded += 1
    return {"status": "saved", "recorded": recorded, "submitted": len(issues)}


@router.delete("/{company_id}/issues/{issue_id}")
def delete_issue(company_id: UUID, issue_id: UUID,
                 p: Principal = Depends(require_role("COMPANY_USER"))):
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        used = fetch_one(conn, """
            SELECT 1 FROM assess.scenarios WHERE issue_id=%s LIMIT 1""", (str(issue_id),))
        if used is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "An assessment was run against this issue, so it cannot be removed. "
                "Assessments are immutable records of what was considered at the time.")
        deleted = fetch_one(conn, """
            DELETE FROM company.issues WHERE issue_id=%s AND company_id=%s
            RETURNING issue_id""", (str(issue_id), str(company_id)))
        if deleted is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found.")
    return {"status": "deleted"}
