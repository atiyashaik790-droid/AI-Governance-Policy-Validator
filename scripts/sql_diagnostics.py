"""Allowlisted diagnostic labels only. Never serialize exception text or arguments."""

import re


DESCRIPTIONS = {
    "SQL_FIREWALL_DENIED": "Azure SQL rejected this client's network access.",
    "SQL_LOGIN_DENIED": "SQL login failed; check the approved identity and database user mapping.",
    "SQL_DATABASE_ACCESS_DENIED": "Database is unavailable to this identity or the target database is incorrect.",
    "SQL_PERMISSION_DENIED": "A required SQL read or metadata permission was denied.",
    "SQL_OBJECT_MISSING_OR_NOT_VISIBLE": "A required SQL object is absent or not visible to this identity.",
    "ODBC_DRIVER_UNAVAILABLE": "Required ODBC driver or its shared libraries are unavailable.",
    "TLS_VALIDATION_FAILED": "ODBC could not validate the SQL server TLS certificate.",
    "SQL_CONNECTION_TIMEOUT": "SQL connection or query timed out.",
    "SQL_TRANSPORT_FAILURE": "ODBC could not establish or maintain the SQL connection.",
    "TOKEN_ACQUISITION_UNAVAILABLE": "The existing Azure CLI context could not obtain a token.",
    "IDENTITY_PIN_OR_EXPIRY_MISMATCH": "Token identity or remaining lifetime does not match the approved SQL configuration.",
    "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE": "A schema query or verifier implementation failed; do not infer a permission problem.",
}


def chain(error):
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attr in ("orig", "__cause__", "__context__"):
            child = getattr(current, attr, None)
            if isinstance(child, BaseException):
                pending.append(child)


def classify(error, stage):
    states, codes = set(), set()
    messages = []
    schema = None
    for current in chain(error):
        if getattr(current, "safe_diagnostic", None):
            schema = current.safe_diagnostic
        # Read internally for classification only. Raw arguments never enter output.
        for arg in getattr(current, "args", ()):
            if not isinstance(arg, str):
                continue
            messages.append(arg.lower())
            if re.fullmatch(r"[A-Z0-9]{5}", arg):
                states.add(arg)
            states.update(re.findall(r"\[([A-Z0-9]{5})\]", arg))
            codes.update(int(v) for v in re.findall(r"\((\d{1,6})\)", arg))
    native = next(
        (c for c in [40615, 18456, 4060, 916, 229, 230, 297, 208, 207] if c in codes),
        None,
    )
    categories = {
        40615: "SQL_FIREWALL_DENIED",
        18456: "SQL_LOGIN_DENIED",
        4060: "SQL_DATABASE_ACCESS_DENIED",
        916: "SQL_DATABASE_ACCESS_DENIED",
        229: "SQL_PERMISSION_DENIED",
        230: "SQL_PERMISSION_DENIED",
        297: "SQL_PERMISSION_DENIED",
        208: "SQL_OBJECT_MISSING_OR_NOT_VISIBLE",
        207: "SQL_OBJECT_MISSING_OR_NOT_VISIBLE",
    }
    text = " ".join(messages)
    if native:
        category = categories[native]
    elif states & {"IM002", "IM003"}:
        category = "ODBC_DRIVER_UNAVAILABLE"
    elif "certificate" in text and ("ssl" in text or "tls" in text):
        category = "TLS_VALIDATION_FAILED"
    elif states & {"HYT00", "HYT01"}:
        category = "SQL_CONNECTION_TIMEOUT"
    elif states & {"08001", "08S01", "08003", "08004"}:
        category = "SQL_TRANSPORT_FAILURE"
    elif "unexpired token for the configured" in text:
        category = "IDENTITY_PIN_OR_EXPIRY_MISMATCH"
    elif "authentication unavailable" in text:
        category = "TOKEN_ACQUISITION_UNAVAILABLE"
    elif schema:
        category = schema["category"]
    elif stage == "configuration":
        category = "SQL_CONFIGURATION_INVALID"
    else:
        category = (
            "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE"
            if stage == "schema"
            else "SQL_CONNECTION_UNCLASSIFIED"
        )
    result = {
        "category": category,
        "stage": stage,
        "detail": DESCRIPTIONS.get(
            category, "A reviewed schema/configuration requirement failed."
        ),
    }
    allowed_states = {
        "28000",
        "42000",
        "42S02",
        "42S22",
        "HY000",
        "HYT00",
        "HYT01",
        "08001",
        "08S01",
        "08003",
        "08004",
        "IM002",
        "IM003",
    }
    result["sqlstates"] = sorted(states & allowed_states)
    if native:
        result["native_code"] = native
    if schema and schema.get("object"):
        result["schema_object"] = schema["object"]
    return result
