"""Reference pipeline: bronze/class_survey_raw.csv -> silver/ -> gold/.

One reasonable set of rules. Other choices are valid; writing them down is the point.

Silver rules
  1. Trim and standardise every text value; map spellings to dim_city / drink / device.
  2. Reject (quarantine, never drop silently) a row whose city is unknown, whose birthday is after
     the submission, or whose coffee is negative. Each rejected row keeps its raw values + reason.
  3. One row per student: among valid rows, the latest submitted_at wins (a resubmission corrects).
  4. Unparseable birthday or coffee -> blank, not rejected. Slash and dash dates are day first.
  5. Coffee: "2-3" -> 2.5, "10+" -> 10, "every day" -> 7, words -> numbers. Over 21/week is kept
     but flagged coffee_is_outlier (3 a day is the plausible ceiling).
  6. Lineage columns: _loaded_at (processing time, UTC) and _source_file.
Gold excludes coffee outliers and blanks from coffee statistics, and says so in its columns.
"""
import csv
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = "bronze/class_survey_raw.csv"
LOADED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
OUTLIER_CUPS = 21

DIM_CITY = {  # city -> (province, island)
    "Yogyakarta": ("DI Yogyakarta", "Java"), "Sleman": ("DI Yogyakarta", "Java"),
    "Jakarta": ("DKI Jakarta", "Java"), "Bekasi": ("West Java", "Java"), "Bandung": ("West Java", "Java"),
    "Semarang": ("Central Java", "Java"), "Solo": ("Central Java", "Java"),
    "Surabaya": ("East Java", "Java"), "Malang": ("East Java", "Java"),
    "Medan": ("North Sumatra", "Sumatra"), "Makassar": ("South Sulawesi", "Sulawesi"), "Denpasar": ("Bali", "Bali"),
}
CITY_ALIASES = {
    "jogja": "Yogyakarta", "yogya": "Yogyakarta", "jogjakarta": "Yogyakarta", "yk": "Yogyakarta",
    "kab. sleman": "Sleman", "jkt": "Jakarta", "dki jakarta": "Jakarta", "jakarta selatan": "Jakarta",
    "jaksel": "Jakarta", "bdg": "Bandung", "sby": "Surabaya", "smg": "Semarang", "surakarta": "Solo",
    "ujung pandang": "Makassar", "bali": "Denpasar",
}
DRINKS = {
    "Coffee": {"coffee", "kopi", "kopi susu", "latte", "americano"},
    "Tea": {"tea", "teh", "es teh", "es teh manis", "green tea"},
    "Matcha": {"matcha", "matcha latte"}, "Boba": {"boba", "bubble tea"}, "Water": {"water", "air putih"},
}
DEVICES = {"android": "Android", "samsung": "Android", "iphone": "iOS", "ios": "iOS"}
WORDS = {"none": 0, "one": 1, "two": 2, "three": 3, "five": 5, "every day": 7}
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d %b %Y", "%b %d %Y", "%d %B %Y"]


def city(raw):
    v = raw.strip().lower()
    name = CITY_ALIASES.get(v) or next((c for c in DIM_CITY if c.lower() == v), None)
    return name


def drink(raw):
    v = raw.strip().lower()
    return next((k for k, names in DRINKS.items() if v in names), None)


def birthday(raw):
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), f).date()
        except ValueError:
            pass
    return None


def coffee(raw):
    v = raw.strip().lower().replace(",", ".").replace("cups", "").strip()
    if v in WORDS:
        return float(WORDS[v])
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", v):
        return (float(m[1]) + float(m[2])) / 2
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\+", v):
        return float(m[1])
    try:
        return float(v)
    except ValueError:
        return None


def age_on(born, day):
    return day.year - born.year - ((day.month, day.day) < (born.month, born.day))


def write(path, header, rows):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def num(x):
    return "" if x is None else f"{x:g}"


# ── Silver ────────────────────────────────────────────────────────────────────
bronze = list(csv.DictReader(open(HERE / SOURCE, encoding="utf-8")))
valid, rejected = [], []
for r in bronze:
    submitted = datetime.strptime(r["submitted_at"], "%Y-%m-%d %H:%M:%S")
    c, b, cups = city(r["hometown"]), birthday(r["birthday"]), coffee(r["coffee_per_week"])
    reason = ("city_unknown" if c is None else
              "birthday_in_future" if b and b > submitted.date() else
              "coffee_negative" if cups is not None and cups < 0 else None)
    if reason:
        rejected.append([r[k] for k in r] + [reason, LOADED_AT, SOURCE])
        continue
    valid.append({
        "student_id": r["student_id"].strip(), "submitted_at": submitted, "response_id": r["response_id"],
        "city": c, "birthday": b, "age": age_on(b, submitted.date()) if b else None,
        "coffee_per_week": cups, "coffee_is_outlier": cups is not None and cups > OUTLIER_CUPS,
        "favorite_drink": drink(r["favorite_drink"]), "device_os": DEVICES.get(r["device"].strip().lower()),
    })

latest = {}
for v in sorted(valid, key=lambda v: v["submitted_at"]):
    latest[v["student_id"]] = v                       # later submission overwrites earlier
silver = sorted(latest.values(), key=lambda v: v["student_id"])
duplicates_resolved = len(valid) - len(silver)

write(HERE / "silver" / "survey_response.csv",
      ["student_id", "response_id", "submitted_at", "city", "birthday", "age", "coffee_per_week",
       "coffee_is_outlier", "favorite_drink", "device_os", "_loaded_at", "_source_file"],
      [[s["student_id"], s["response_id"], s["submitted_at"].strftime("%Y-%m-%d %H:%M:%S"), s["city"],
        s["birthday"].isoformat() if s["birthday"] else "", "" if s["age"] is None else s["age"],
        num(s["coffee_per_week"]), str(s["coffee_is_outlier"]).lower(), s["favorite_drink"] or "",
        s["device_os"] or "", LOADED_AT, SOURCE] for s in silver])
write(HERE / "silver" / "survey_rejected.csv", list(bronze[0].keys()) + ["reject_reason", "_loaded_at", "_source_file"], rejected)
write(HERE / "silver" / "dim_city.csv", ["city", "province", "island"],
      [[c, p, i] for c, (p, i) in sorted(DIM_CITY.items())])

nulls = {col: sum(s[col] is None for s in silver) for col in ("birthday", "coffee_per_week", "favorite_drink", "device_os")}
dq = [["bronze_rows", len(bronze)], ["rejected_rows", len(rejected)], ["duplicates_resolved", duplicates_resolved],
      ["silver_rows", len(silver)], ["coffee_outliers_flagged", sum(s["coffee_is_outlier"] for s in silver)]]
dq += [[f"null_{k}", v] for k, v in nulls.items()]
dq += [[f"rejected_{k}", v] for k, v in sorted(Counter(r[-3] for r in rejected).items())]
assert len(bronze) == len(silver) + len(rejected) + duplicates_resolved, "row accounting does not add up"
write(HERE / "silver" / "_dq_report.csv", ["metric", "value"], dq)

# ── Gold ──────────────────────────────────────────────────────────────────────
total = len(silver)
per_city = Counter(s["city"] for s in silver)
write(HERE / "gold" / "students_by_region.csv", ["province", "city", "students", "share_of_class_pct"],
      sorted([[DIM_CITY[c][0], c, n, round(100 * n / total, 1)] for c, n in per_city.items()],
             key=lambda r: (-r[2], r[1])))

cups_by_city = defaultdict(list)
for s in silver:
    if s["coffee_per_week"] is not None and not s["coffee_is_outlier"]:
        cups_by_city[s["city"]].append(s["coffee_per_week"])
write(HERE / "gold" / "coffee_by_city.csv",
      ["city", "answers_used", "avg_cups", "median_cups", "min_cups", "max_cups", "excluded_blank_or_outlier"],
      sorted([[c, len(v), round(statistics.mean(v), 2), num(statistics.median(v)), num(min(v)), num(max(v)),
               per_city[c] - len(v)] for c, v in cups_by_city.items()], key=lambda r: -r[1]))


def age_group(a):
    return "unknown" if a is None else "20 or under" if a <= 20 else "21-22" if a <= 22 else "23-24" if a <= 24 else "25+"


groups = defaultdict(Counter)
for s in silver:
    groups[age_group(s["age"])][s["favorite_drink"] or "unknown"] += 1
order = ["20 or under", "21-22", "23-24", "25+", "unknown"]
write(HERE / "gold" / "drink_preference_by_age_group.csv", ["age_group", "favorite_drink", "students", "pct_within_group"],
      [[g, d, n, round(100 * n / sum(groups[g].values()), 1)]
       for g in order if g in groups for d, n in groups[g].most_common()])

for k, v in dq:
    print(f"{k:28} {v}")
print("top region:", per_city.most_common(3))
