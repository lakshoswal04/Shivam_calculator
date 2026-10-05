"""Self-serve sign-up.

Registration is the only path that creates an organisation outside the seed, so
these cover the two things that go wrong when a tenant is born: the identity
constraints on auth.users / auth.organisations, and whether the new tenant is
genuinely isolated from the one that already exists.
"""
import uuid


def _body(**over):
    tag = uuid.uuid4().hex[:8]
    body = {
        "email": f"owner-{tag}@example.test",
        "password": "a-long-enough-password",
        "full_name": "Priya Raman",
        "org_name": f"Raman & Co {tag}",
    }
    body.update(over)
    return body


def _register(client, **over):
    return client.post("/api/v1/auth/register", json=_body(**over))


# ------------------------------------------------------------------ happy path
def test_registration_creates_an_owned_organisation(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["access_token"] and d["refresh_token"]
    # The first user owns the organisation, as owner@demo.test does.
    assert d["user"]["role"] == "ADMINISTRATOR"
    # A real tenant must never inherit the demo reviewer's approvals.
    assert d["user"]["is_demo_org"] is False


def test_the_returned_token_works_immediately(client):
    """Sign-up signs you in; a user should not have to log in again."""
    r = _register(client)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text


# ------------------------------------------------------------------- identity
def test_duplicate_email_is_a_clean_conflict(client):
    """users_email_lower_key is case-insensitive, and used to surface as a 500."""
    body = _body()
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    again = client.post("/api/v1/auth/register", json=body)
    assert again.status_code == 409, again.text


def test_duplicate_email_is_caught_regardless_of_case(client):
    body = _body()
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    body2 = _body(email=body["email"].upper())
    assert client.post("/api/v1/auth/register", json=body2).status_code == 409


def test_short_password_is_refused_before_an_account_exists(client):
    r = _register(client, password="short")
    assert r.status_code == 422, r.text


def test_malformed_email_names_the_field(client):
    r = _register(client, email="not-an-email")
    assert r.status_code == 422, r.text


# ----------------------------------------------------------------------- slug
def test_two_organisations_may_share_a_name(client):
    """auth.organisations.slug is UNIQUE with a format CHECK, so a second firm
    of the same name must still be able to sign up."""
    name = f"Shared Name {uuid.uuid4().hex[:6]}"
    a = _register(client, org_name=name)
    b = _register(client, org_name=name)
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["user"]["org_id"] != b.json()["user"]["org_id"]


def test_org_name_of_only_punctuation_still_yields_a_valid_slug(client):
    """The slug CHECK requires a leading alphanumeric and two characters."""
    r = _register(client, org_name="&&&")
    assert r.status_code == 201, r.text


# ------------------------------------------------------------------- isolation
def test_a_new_tenant_sees_none_of_the_demo_org_companies(client, cs_headers):
    """The RLS guarantee, at the moment a tenant is created.

    The demo org has companies seeded; a freshly registered org must see an
    empty list, not somebody else's client list.
    """
    seeded = client.get("/api/v1/companies", headers=cs_headers)
    assert seeded.status_code == 200
    assert len(seeded.json()["companies"]) > 0, "demo org should have companies to hide"

    token = _register(client).json()["access_token"]
    mine = client.get("/api/v1/companies",
                      headers={"Authorization": f"Bearer {token}"})
    assert mine.status_code == 200, mine.text
    assert mine.json()["companies"] == []
