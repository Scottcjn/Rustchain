# Self-Audit Report: machine_passport.py

**File:** `node/machine_passport.py`
**Lines:** 975
**Commit:** 22d3b41
**Author:** BossChaos
**Wallet:** RTC6d1f27d28961279f1034d9561c2403697eb55602

---

## Vulnerability Summary

| # | Severity | Vulnerability | Location | CVSS 3.1 |
|---|----------|---------------|----------|----------|
| 1 | 🟠 MEDIUM | No Authentication on Passport Operations — Arbitrary CRUD | Lines 262-397 | 6.5 |
| 2 | 🟠 MEDIUM | Exception Detail Disclosure in Error Responses | Lines 296, 366, 395 | 5.3 |
| 3 | 🟠 MEDIUM | Unsanitized User Input in PDF Generation | Lines 697-730 | 6.1 |
| 4 | 🟡 LOW | No Input Validation on MachinePassport Dataclass | Lines 45-94 | 4.3 |
| 5 | 🟡 LOW | No Access Control — Any Caller Can Modify/Delete Any Passport | Lines 328-397 | 4.3 |

---

## Finding #1: No Authentication on Passport Operations (MEDIUM)

**Location:** `MachinePassportLedger.create_passport()`, `update_passport()`, `delete_passport()` — Lines 262-397

**Description:**

The `MachinePassportLedger` class provides full CRUD operations on machine passports without any authentication or authorization checks. The methods accept input data directly and perform database operations:

```python
def create_passport(self, passport: MachinePassport) -> Tuple[bool, str]:
    with self._get_connection() as conn:
        conn.execute("""INSERT INTO machine_passports ...""", (...))
        conn.commit()
        return True, f"Passport created for machine {passport.machine_id}"
```

```python
def delete_passport(self, machine_id: str) -> Tuple[bool, str]:
    with self._get_connection() as conn:
        conn.execute("DELETE FROM machine_passports WHERE machine_id = ?", (machine_id,))
        conn.commit()
        return True, f"Passport deleted for machine {machine_id}"
```

There is no caller verification, no ownership check, and no rate limiting. Any caller with access to the ledger can create, modify, or delete any machine passport.

**Impact:** An attacker can:
- Create fraudulent machine passports
- Modify existing passports (change owner, architecture, provenance)
- Delete legitimate passports (denial of service)
- Inject false repair history and attestation records

**Remediation:**
- Add authentication: require API key or bearer token for write operations
- Implement ownership checks: only the passport owner can modify/delete their own passport
- Add audit logging for all write operations

---

## Finding #2: Exception Detail Disclosure (MEDIUM)

**Location:** Lines 296, 366, 395

**Description:**

All database operations return raw exception messages to the caller:

```python
except sqlite3.IntegrityError as e:
    return False, f"Passport already exists: {e}"
except Exception as e:
    return False, f"Database error: {e}"
```

These messages reveal database schema details (constraint names, column names, table structure) and file system paths. An attacker can trigger specific errors to map the database schema.

**Impact:** Information disclosure aids in planning further attacks against the database.

**Remediation:** Return generic error messages; log detailed errors server-side only.

---

## Finding #3: Unsanitized User Input in PDF Generation (MEDIUM)

**Location:** `generate_passport_pdf()` — Lines 697-730

**Description:**

```python
details_data = [
    ['Machine ID:', passport.get('machine_id', 'N/A')],
    ['Name:', passport.get('name', 'N/A')],
    ['Owner:', passport.get('owner_miner_id', 'N/A')],
    ['Architecture:', passport.get('architecture', 'N/A')],
    ['Manufacture Year:', str(passport.get('manufacture_year', 'N/A'))],
    ['Provenance:', passport.get('provenance', 'N/A')],
]
```

User-provided fields are passed directly into the PDF document without sanitization. ReportLab's `Paragraph` class supports a subset of HTML/XML markup. If a user sets their `name` or `provenance` field to contain ReportLab markup (e.g., `<font color="red">` or `<img src="..."/>`), the generated PDF could render unintended content.

Additionally, the repair log entries (`description`, `repair_type`, `parts_replaced`) are also unsanitized.

**Impact:** PDF content manipulation, potential information disclosure through injected markup. While this is primarily a display issue, it could be used to create misleading or fraudulent passport documents.

**Remediation:**
- Sanitize user input before passing to ReportLab
- Use `Paragraph` with plain text mode, or escape special characters (`<`, `>`, `&`)
- Validate and truncate input fields to reasonable lengths

---

## Finding #4: No Input Validation on MachinePassport Dataclass (LOW)

**Location:** `MachinePassport.__post_init__()` — Lines 65-77

**Description:**

```python
@dataclass
class MachinePassport:
    machine_id: str
    name: str
    owner_miner_id: Optional[str] = None
    manufacture_year: Optional[int] = None
    architecture: Optional[str] = None
    ...

    def __post_init__(self):
        if not self.machine_id or len(self.machine_id) > 64:
            raise ValueError("machine_id must be between 1 and 64 characters")
```

Only `machine_id` has validation (length check). All other fields (`name`, `owner_miner_id`, `architecture`, `provenance`, `photo_url`) are accepted without any validation:
- No length limits on text fields
- No URL validation on `photo_url`
- No range check on `manufacture_year` (could be negative or future dates)
- No character restrictions

**Impact:** Arbitrary data can be stored, potentially leading to database bloat or display issues.

**Remediation:**
- Add validation for all fields: length limits, format checks, range constraints
- Validate `photo_url` as a valid URL
- Restrict `manufacture_year` to reasonable range (1950-2030)

---

## Finding #5: No Access Control on Passport Modification (LOW)

**Location:** `update_passport()`, `delete_passport()` — Lines 328-397

**Description:**

Even if authentication were added, the `update_passport()` and `delete_passport()` methods do not verify that the caller owns the passport being modified:

```python
def update_passport(self, machine_id: str, updates: Dict) -> Tuple[bool, str]:
    # No ownership check!
    conn.execute(f"UPDATE machine_passports SET ... WHERE machine_id = ?", values)
```

Any authenticated caller could modify or delete any other user's passport.

**Impact:** Unauthorized modification or deletion of other users' machine passports.

**Remediation:**
- Add ownership verification: `WHERE machine_id = ? AND owner_miner_id = ?`
- Implement role-based access control (admin can modify any passport)

---

## Conclusion

The `machine_passport.py` module provides a machine identity registry with PDF export capabilities. The most significant findings are the lack of authentication (Finding #1) and the unsanitized input in PDF generation (Finding #3). The module is well-structured with parameterized queries (preventing SQL injection), but the missing access controls and input validation represent significant security gaps.

Priority fixes:
1. **Add authentication and ownership checks** to all write operations (Findings #1, #5)
2. **Sanitize user input** before PDF generation (Finding #3)
3. **Sanitize error messages** — prevent detail disclosure (Finding #2)
