import re

_CODE_RE = re.compile(r"^[a-z0-9-]{3,32}$")


def normalize_company_code(raw: str) -> str:
    return (raw or "").strip().lower()


def is_valid_company_code(code: str) -> bool:
    return bool(_CODE_RE.match(code))


def get_active_org(conn, raw_company_code: str):
    code = normalize_company_code(raw_company_code)
    if not code:
        return None
    return conn.execute(
        "SELECT * FROM organizations WHERE company_code=%s AND status='active'",
        (code,),
    ).fetchone()
