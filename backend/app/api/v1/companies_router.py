"""Company records within the signed-in organisation."""
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from ...db import fetch_all, fetch_one, tx
from ...deps import Principal, current_principal, require_company_access, require_role
from ...schemas import CapitalIn, CompanyCreate, HoldingIn

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
    return {"company": co, "classification": cls, "capital": cap, "holdings": holdings}


@router.get("")
def list_companies(p: Principal = Depends(current_principal)):
    with tx(p.org_id) as conn:
        rows = fetch_all(conn, """
            SELECT c.company_id, c.name, c.cin, c.incorporation_date,
                   cc.company_type, cc.listed_status, cc.exchanges, cc.is_sme,
                   cs.authorised_capital, cs.issued_capital, cs.paid_up_capital,
                   cs.face_value, cs.shares_issued
            FROM company.companies c
            LEFT JOIN LATERAL (
              SELECT * FROM company.company_classifications x
              WHERE x.company_id=c.company_id ORDER BY effective_from DESC LIMIT 1) cc ON true
            LEFT JOIN LATERAL (
              SELECT * FROM company.capital_snapshots x
              WHERE x.company_id=c.company_id ORDER BY as_of_date DESC LIMIT 1) cs ON true
            ORDER BY c.name""")
    return {"companies": rows}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyCreate,
                   p: Principal = Depends(require_role("COMPANY_USER"))):
    with tx(p.org_id) as conn:
        if body.cin:
            dup = fetch_one(conn, "SELECT company_id FROM company.companies WHERE cin=%s",
                            (body.cin,))
            if dup:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    "A company with this CIN already exists in your organisation.")
        row = fetch_one(conn, """
            INSERT INTO company.companies (org_id, name, cin, incorporation_date)
            VALUES (%s,%s,%s,%s) RETURNING company_id, name, cin""",
            (p.org_id, body.name, body.cin, body.incorporation_date))
        conn.execute("""
            INSERT INTO company.company_classifications
              (org_id, company_id, company_type, listed_status, exchanges, is_sme, effective_from)
            VALUES (%s,%s,%s,%s,%s::legal.exchange[],%s,%s)""",
            (p.org_id, row["company_id"], body.company_type, body.listed_status,
             body.exchanges, body.is_sme, body.incorporation_date or date.today()))
    return row


@router.get("/{company_id}")
def get_company(company_id: UUID, p: Principal = Depends(current_principal)):
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        return company_facts(conn, str(company_id))


@router.put("/{company_id}/capital")
def set_capital(company_id: UUID, body: CapitalIn,
                p: Principal = Depends(require_role("FINANCE_USER"))):
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
                 p: Principal = Depends(require_role("FINANCE_USER"))):
    with tx(p.org_id) as conn:
        require_company_access(conn, p, str(company_id))
        sc = fetch_one(conn, """SELECT share_class_id FROM company.share_classes
                                WHERE company_id=%s ORDER BY name LIMIT 1""", (str(company_id),))
        if sc is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Record the capital structure before the cap table.")
        conn.execute("""DELETE FROM company.shareholders WHERE company_id=%s""", (str(company_id),))
        for h in holdings:
            row = fetch_one(conn, """
                INSERT INTO company.shareholders
                  (org_id, company_id, name, category, is_promoter)
                VALUES (%s,%s,%s,%s,%s) RETURNING shareholder_id""",
                (p.org_id, str(company_id), h.name, h.category or "PUBLIC", h.is_promoter))
            conn.execute("""
                INSERT INTO company.holdings
                  (org_id, shareholder_id, share_class_id, as_of_date, shares_held)
                VALUES (%s,%s,%s,%s,%s)""",
                (p.org_id, row["shareholder_id"], sc["share_class_id"],
                 date.today(), h.shares_held))
    return {"status": "saved", "holders": len(holdings)}
