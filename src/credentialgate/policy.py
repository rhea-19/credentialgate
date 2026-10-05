"""The service's only disclosure policy. Clients cannot supply their own role."""

PUBLIC_FIELDS = frozenset({"display_name", "profession", "jurisdiction"})
INSTITUTION_FIELDS = PUBLIC_FIELDS | {"license_number", "institution", "license_expires_at"}
REVIEWER_FIELDS = INSTITUTION_FIELDS | {"contact_email", "date_of_birth"}
ROLE_FIELDS = {
    "public": PUBLIC_FIELDS,
    "institution": INSTITUTION_FIELDS,
    "reviewer": REVIEWER_FIELDS,
}


def authorize(principal: dict, tenant: str, requested: list[str]) -> bool:
    role = principal["role"]
    if role not in ROLE_FIELDS:
        return False
    if role != "public" and principal["tenant"] != tenant:
        return False
    return set(requested) <= ROLE_FIELDS[role]
