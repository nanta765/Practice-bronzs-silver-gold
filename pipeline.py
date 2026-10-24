#!/usr/bin/env python3
"""
Medallion practice pipeline: bronze -> silver -> gold.

One script rebuilds silver and gold from bronze.
Run:  python3 pipeline.py

CONTRACT (README rule 3):
    bronze rows = silver rows + rejected rows + duplicates removed

DESIGN DECISIONS (README rule 2 - every decision is written down here).
Only the standard library is used so the script runs anywhere with python3.

Column-by-column rules are documented next to the function that applies them.
Nothing is ever dropped silently: a bronze row ends up in exactly one of
    - silver/survey_response.csv   (accepted, one row per student)
    - silver/survey_rejected.csv   (refused, with raw values + reject_reason)
    - "duplicates removed" count    (a later submission by a student we already kept)
"""

import csv
import os
import statistics
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Paths. Resolved relative to this script so it runs from any working dir.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
BRONZE_FILE = os.path.join(HERE, "bronze", "class_survey_raw.csv")
SILVER_DIR = os.path.join(HERE, "silver")
GOLD_DIR = os.path.join(HERE, "gold")

SILVER_RESPONSE = os.path.join(SILVER_DIR, "survey_response.csv")
SILVER_REJECTED = os.path.join(SILVER_DIR, "survey_rejected.csv")
SILVER_REF_CITY = os.path.join(SILVER_DIR, "ref_city.csv")

GOLD_BY_REGION = os.path.join(GOLD_DIR, "students_by_region.csv")
GOLD_COFFEE_BY_CITY = os.path.join(GOLD_DIR, "coffee_by_city.csv")
GOLD_DRINK_BY_AGE = os.path.join(GOLD_DIR, "drink_preference_by_age_group.csv")

SOURCE_FILE = "bronze/class_survey_raw.csv"

# ---------------------------------------------------------------------------
# REFERENCE DATA: city -> (canonical city, province, island)
#
# DECISION: hometowns are written many ways (case, spacing, abbreviations,
# local names). We map every known spelling to one canonical city. The map
# key is the raw value lower-cased and stripped of surrounding spaces.
# Cities we cannot recognise are rejected (reason: unknown_hometown) rather
# than guessed, so the region report is trustworthy.
#
# DECISION: "Jogja / YK / Yogyakarta / Sleman / Kab. Sleman" all collapse to
# Yogyakarta. Sleman is a regency inside the Yogyakarta Special Region, and
# for a class survey treating it as Yogyakarta keeps the region table simple.
# "Solo / Surakarta" -> Surakarta. "Ujung Pandang" -> Makassar (old name).
# "Jakarta / JKT / Jaksel / Jakarta Selatan / DKI Jakarta" -> Jakarta.
# ---------------------------------------------------------------------------
CITY_REF = {
    # canonical : (city, province, island)
    "Yogyakarta": ("Yogyakarta", "DI Yogyakarta", "Jawa"),
    "Jakarta": ("Jakarta", "DKI Jakarta", "Jawa"),
    "Bandung": ("Bandung", "Jawa Barat", "Jawa"),
    "Bekasi": ("Bekasi", "Jawa Barat", "Jawa"),
    "Semarang": ("Semarang", "Jawa Tengah", "Jawa"),
    "Surakarta": ("Surakarta", "Jawa Tengah", "Jawa"),
    "Surabaya": ("Surabaya", "Jawa Timur", "Jawa"),
    "Malang": ("Malang", "Jawa Timur", "Jawa"),
    "Medan": ("Medan", "Sumatera Utara", "Sumatera"),
    "Makassar": ("Makassar", "Sulawesi Selatan", "Sulawesi"),
    "Denpasar": ("Denpasar", "Bali", "Bali"),
}

# raw spelling (lower-cased, stripped) -> canonical city
CITY_ALIASES = {
    # Yogyakarta family
    "yogya": "Yogyakarta",
    "jogja": "Yogyakarta",
    "yogyakarta": "Yogyakarta",
    "jogjakarta": "Yogyakarta",
    "yk": "Yogyakarta",
    "kab. sleman": "Yogyakarta",
    "sleman": "Yogyakarta",
    # Jakarta family
    "jakarta": "Jakarta",
    "dki jakarta": "Jakarta",
    "jkt": "Jakarta",
    "jaksel": "Jakarta",
    "jakarta selatan": "Jakarta",
    # Bandung
    "bandung": "Bandung",
    "bdg": "Bandung",
    # Bekasi
    "bekasi": "Bekasi",
    # Semarang
    "semarang": "Semarang",
    "smg": "Semarang",
    # Surakarta / Solo
    "solo": "Surakarta",
    "surakarta": "Surakarta",
    # Surabaya
    "surabaya": "Surabaya",
    "sby": "Surabaya",
    # Malang
    "malang": "Malang",
    # Medan
    "medan": "Medan",
    # Makassar
    "makassar": "Makassar",
    "ujung pandang": "Makassar",
    # Denpasar / Bali
    "denpasar": "Denpasar",
    "bali": "Denpasar",
}

# ---------------------------------------------------------------------------
# DRINK NORMALISATION
# DECISION: collapse spellings and local names to a small canonical set.
#   boba / bubble tea / boba           -> boba
#   coffee / kopi / Coffee             -> coffee
#   kopi susu                          -> kopi susu (milk coffee, kept distinct)
#   tea / teh / es teh / es teh manis  -> tea
#   green tea                          -> green tea
#   matcha / matcha latte              -> matcha
#   americano                          -> americano
#   latte                              -> latte
#   water / air putih                  -> water
# Blank drink is allowed (not a reject): recorded as "" because the student
# row is still usable for the region report. favorite_drink is optional.
# ---------------------------------------------------------------------------
DRINK_ALIASES = {
    "boba": "boba",
    "bubble tea": "boba",
    "coffee": "coffee",
    "kopi": "coffee",
    "kopi susu": "kopi susu",
    "tea": "tea",
    "teh": "tea",
    "es teh": "tea",
    "es teh manis": "tea",
    "green tea": "green tea",
    "matcha": "matcha",
    "matcha latte": "matcha",
    "americano": "americano",
    "latte": "latte",
    "water": "water",
    "air putih": "water",
}

# ---------------------------------------------------------------------------
# DEVICE NORMALISATION
# DECISION: map every value to a platform. samsung/android/ANDROID -> Android;
# ios/iphone/iPhone/iOS -> iOS. (Samsung phones run Android.)
# ---------------------------------------------------------------------------
DEVICE_ALIASES = {
    "samsung": "Android",
    "android": "Android",
    "ios": "iOS",
    "iphone": "iOS",
}

# ---------------------------------------------------------------------------
# COFFEE WORD NUMBERS
# DECISION: spelled-out small numbers are accepted and converted.
# ---------------------------------------------------------------------------
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Coffee bounds (README "Go further" sanity). DECISION: a plausible weekly
# cups range is 0..35 (5/day). Values outside this (e.g. 50) are rejected.
COFFEE_MIN, COFFEE_MAX = 0, 35

# Birthday plausibility. DECISION: a class survey in 2026; accept births
# 1990-01-01 .. 2012-12-31. Future dates (e.g. 2027) are rejected.
BIRTH_MIN = date(1990, 1, 1)
BIRTH_MAX = date(2012, 12, 31)


def clean_device(raw):
    """Return canonical platform, or None if unknown."""
    return DEVICE_ALIASES.get((raw or "").strip().lower())


def clean_city(raw):
    """Return (city, province, island) or None if the hometown is unknown."""
    key = (raw or "").strip().lower()
    canonical = CITY_ALIASES.get(key)
    if canonical is None:
        return None
    return CITY_REF[canonical]


def clean_drink(raw):
    """Return canonical drink. Blank -> "" (allowed). Unknown -> None."""
    key = (raw or "").strip().lower()
    if key == "":
        return ""  # drink is optional; blank is fine
    return DRINK_ALIASES.get(key)  # None means unknown spelling


def clean_coffee(raw):
    """
    Parse weekly coffee cups into an int, or return ("reject", reason).

    Accepted forms:
      "7", "0 cups", "3 cups"      -> the integer
      "1-2", "9-10", "12-13"       -> midpoint, rounded (1-2 -> 2 via round-half-even? no: use mean then round)
      "0,5", "3,5"                 -> comma decimal, rounded to nearest int
      "12+", "11+"                 -> the number (treat "+" as "at least", keep the number)
      "one".."ten"                 -> word numbers
    Rejected:
      "idk", "none", "?", "every day", "water", "" , negative, out of range
    """
    s = (raw or "").strip().lower()
    if s == "":
        return ("reject", "coffee_blank")

    # strip a trailing "cups" / "cup"
    s = s.replace("cups", "").replace("cup", "").strip()

    # word numbers
    if s in WORD_NUMBERS:
        val = WORD_NUMBERS[s]
        return _coffee_bounds(val, raw)

    # comma decimal -> dot
    s_dot = s.replace(",", ".")

    # "12+" style: keep leading number
    if s_dot.endswith("+"):
        s_dot = s_dot[:-1].strip()

    # range "a-b" -> mean, rounded
    if "-" in s_dot and not s_dot.startswith("-"):
        parts = s_dot.split("-")
        if len(parts) == 2:
            try:
                a = float(parts[0])
                b = float(parts[1])
                val = round((a + b) / 2)
                return _coffee_bounds(val, raw)
            except ValueError:
                return ("reject", "coffee_unparseable")

    # plain number (int or decimal)
    try:
        val = round(float(s_dot))
        return _coffee_bounds(val, raw)
    except ValueError:
        return ("reject", "coffee_unparseable")


def _coffee_bounds(val, raw):
    if val < COFFEE_MIN or val > COFFEE_MAX:
        return ("reject", "coffee_out_of_range")
    return val


def clean_birthday(raw):
    """
    Parse a birthday into a date, or return ("reject", reason).

    DECISION: many formats appear. We try an explicit list of formats.
    Day/month ambiguity: dd/mm/yyyy and dd-mm-yyyy are read DAY first, which
    is the Indonesian convention and is consistent with values like 28/10 and
    13/09 that cannot be months. 2-digit years (yy) are read via %y which maps
    00-68 -> 2000-2068, good enough for this student cohort.
    Blank -> reject (we need an age for the "go further" age-group report, and
    a trusted student row should have a parseable birthday).
    Out-of-range (before 1990 or after 2012, incl. the 2027 typos) -> reject.
    """
    s = (raw or "").strip()
    if s == "":
        return ("reject", "birthday_blank")

    formats = [
        "%Y-%m-%d",    # 2001-09-28
        "%Y/%m/%d",    # 2001/01/26
        "%d-%m-%Y",    # 07-06-2003
        "%d/%m/%Y",    # 28/10/2001
        "%d-%m-%y",    # (rare) dd-mm-yy
        "%d/%m/%y",    # 22/03/04
        "%b %d %Y",    # Apr 11 1999
        "%d %b %Y",    # 05 Aug 2002
        "%d %B %Y",    # 13 August 2003
        "%B %d %Y",    # (rare)
    ]
    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(s, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return ("reject", "birthday_unparseable")
    if parsed < BIRTH_MIN or parsed > BIRTH_MAX:
        return ("reject", "birthday_out_of_range")
    return parsed


def age_on(d, ref):
    """Whole years from birthday d to reference date ref."""
    return ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))


def age_group(age):
    """DECISION: simple buckets for the drink-by-age report."""
    if age <= 20:
        return "<=20"
    if age <= 22:
        return "21-22"
    if age <= 24:
        return "23-24"
    return "25+"


def main():
    os.makedirs(SILVER_DIR, exist_ok=True)
    os.makedirs(GOLD_DIR, exist_ok=True)

    # Idempotent timestamp. DECISION: _loaded_at is the only non-deterministic
    # column; everything else is a pure function of bronze, so running twice
    # yields the same rows (rule 1).
    loaded_at = datetime.now().isoformat(timespec="seconds")

    # -----------------------------------------------------------------
    # BRONZE: read raw rows.
    # -----------------------------------------------------------------
    with open(BRONZE_FILE, newline="", encoding="utf-8") as f:
        bronze_rows = list(csv.DictReader(f))

    bronze_count = len(bronze_rows)
    student_ids = {r["student_id"] for r in bronze_rows}
    print(f"BRONZE: {bronze_count} rows, {len(student_ids)} unique students")

    # -----------------------------------------------------------------
    # SILVER: clean, reject, de-duplicate.
    #
    # DECISION on duplicates: one row per student (rule). The same student_id
    # can appear more than once (re-submission). We keep the FIRST accepted
    # submission (bronze is ordered by submitted_at ascending) and count every
    # later accepted submission of an already-kept student as a "duplicate
    # removed". A duplicate is NOT written to rejected: it is a valid row we
    # simply already have, tracked separately so the row-accounting balances.
    # -----------------------------------------------------------------
    accepted = []          # list of clean dict rows
    rejected = []          # list of raw dict rows + reject_reason
    seen_students = set()  # student_ids already accepted
    duplicates_removed = 0

    for r in bronze_rows:
        reasons = []

        device = clean_device(r["device"])
        if device is None:
            reasons.append("unknown_device")

        city = clean_city(r["hometown"])
        if city is None:
            reasons.append("unknown_hometown")

        birthday = clean_birthday(r["birthday"])
        if isinstance(birthday, tuple):  # ("reject", reason)
            reasons.append(birthday[1])

        coffee = clean_coffee(r["coffee_per_week"])
        if isinstance(coffee, tuple):
            reasons.append(coffee[1])

        drink = clean_drink(r["favorite_drink"])
        if drink is None:
            reasons.append("unknown_drink")

        if reasons:
            rr = dict(r)
            rr["reject_reason"] = ";".join(reasons)
            rejected.append(rr)
            continue

        # Row is clean. Handle duplicate student.
        sid = r["student_id"]
        if sid in seen_students:
            duplicates_removed += 1
            continue
        seen_students.add(sid)

        city_name, province, island = city
        bday = birthday
        age = age_on(bday, date(2026, 10, 24))
        accepted.append({
            "response_id": r["response_id"],
            "student_id": sid,
            "submitted_at": r["submitted_at"],
            "city": city_name,
            "province": province,
            "island": island,
            "birthday": bday.isoformat(),
            "age": age,
            "age_group": age_group(age),
            "coffee_per_week": coffee,
            "favorite_drink": drink,
            "device": device,
            "_loaded_at": loaded_at,
            "_source_file": SOURCE_FILE,
        })

    # -----------------------------------------------------------------
    # Write silver/survey_response.csv (one row per student).
    # DECISION: sort by student_id for a stable, idempotent file order.
    # -----------------------------------------------------------------
    accepted.sort(key=lambda x: x["student_id"])
    response_cols = [
        "response_id", "student_id", "submitted_at",
        "city", "province", "island",
        "birthday", "age", "age_group",
        "coffee_per_week", "favorite_drink", "device",
        "_loaded_at", "_source_file",
    ]
    with open(SILVER_RESPONSE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=response_cols)
        w.writeheader()
        w.writerows(accepted)

    # -----------------------------------------------------------------
    # Write silver/survey_rejected.csv (raw values + reject_reason).
    # Keeps the original bronze column order, with reject_reason appended.
    # -----------------------------------------------------------------
    reject_cols = list(bronze_rows[0].keys()) + ["reject_reason"]
    with open(SILVER_REJECTED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=reject_cols)
        w.writeheader()
        w.writerows(rejected)

    # -----------------------------------------------------------------
    # Write silver/ref_city.csv ("go further"): city, province, island.
    # -----------------------------------------------------------------
    with open(SILVER_REF_CITY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["city", "province", "island"])
        for city, province, island in sorted(CITY_REF.values()):
            w.writerow([city, province, island])

    # -----------------------------------------------------------------
    # ROW ACCOUNTING (rule 3): bronze = silver + rejected + duplicates.
    # -----------------------------------------------------------------
    silver_count = len(accepted)
    rejected_count = len(rejected)
    balance = silver_count + rejected_count + duplicates_removed
    print(f"SILVER: {silver_count} accepted, {rejected_count} rejected, "
          f"{duplicates_removed} duplicates removed")
    print(f"BALANCE: {silver_count} + {rejected_count} + {duplicates_removed} "
          f"= {balance} (bronze = {bronze_count}) "
          f"{'OK' if balance == bronze_count else 'MISMATCH!'}")
    assert balance == bronze_count, "row accounting does not balance"

    # -----------------------------------------------------------------
    # GOLD: students_by_region.csv  (students per city+province, % of class).
    # -----------------------------------------------------------------
    region_counts = {}
    for row in accepted:
        key = (row["city"], row["province"])
        region_counts[key] = region_counts.get(key, 0) + 1
    total = silver_count
    region_rows = sorted(region_counts.items(), key=lambda kv: (-kv[1], kv[0][0]))
    with open(GOLD_BY_REGION, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["city", "province", "students", "share_pct"])
        for (city, province), n in region_rows:
            share = round(100 * n / total, 1)
            w.writerow([city, province, n, share])

    # -----------------------------------------------------------------
    # GOLD "go further": coffee_by_city.csv (avg + median cups per city).
    # -----------------------------------------------------------------
    coffee_by_city = {}
    for row in accepted:
        coffee_by_city.setdefault(row["city"], []).append(row["coffee_per_week"])
    with open(GOLD_COFFEE_BY_CITY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["city", "students", "avg_cups_per_week", "median_cups_per_week"])
        for city in sorted(coffee_by_city):
            vals = coffee_by_city[city]
            w.writerow([
                city,
                len(vals),
                round(statistics.mean(vals), 2),
                round(statistics.median(vals), 1),
            ])

    # -----------------------------------------------------------------
    # GOLD "go further": drink_preference_by_age_group.csv
    # Favourite-drink share within each age group. Blank drinks are excluded
    # from the share (they express no preference) but counted nowhere, so each
    # group's shares sum to ~100%.
    # -----------------------------------------------------------------
    group_drink = {}   # age_group -> {drink -> count}
    group_total = {}   # age_group -> count of rows with a drink
    for row in accepted:
        if row["favorite_drink"] == "":
            continue
        g = row["age_group"]
        group_drink.setdefault(g, {})
        group_drink[g][row["favorite_drink"]] = group_drink[g].get(row["favorite_drink"], 0) + 1
        group_total[g] = group_total.get(g, 0) + 1
    group_order = ["<=20", "21-22", "23-24", "25+"]
    with open(GOLD_DRINK_BY_AGE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["age_group", "favorite_drink", "students", "share_pct"])
        for g in group_order:
            if g not in group_drink:
                continue
            drinks = sorted(group_drink[g].items(), key=lambda kv: (-kv[1], kv[0]))
            for drink, n in drinks:
                share = round(100 * n / group_total[g], 1)
                w.writerow([g, drink, n, share])

    print("GOLD: students_by_region.csv, coffee_by_city.csv, "
          "drink_preference_by_age_group.csv written")
    print("DONE.")


if __name__ == "__main__":
    main()
