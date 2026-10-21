"""Generate bronze/class_survey_raw.csv: 300 synthetic, deliberately messy survey answers.

Fixed seed, so every run writes the identical file. No real people: ids, cities and answers are random.
"""
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 2026
STUDENTS = 285          # plus 15 resubmissions = 300 rows
RESUBMISSIONS = 15

# Canonical city -> the ways students type it (weights pick the spelling).
CITY_SPELLINGS = {
    "Yogyakarta": ["Yogyakarta", "yogyakarta", "Jogja", "jogja", "Yogya", "Jogjakarta", "YK", "Jogja "],
    "Sleman": ["Sleman", "sleman", "Kab. Sleman"],
    "Jakarta": ["Jakarta", "jakarta", "JKT", "DKI Jakarta", "Jakarta Selatan", "Jaksel", " Jakarta"],
    "Bandung": ["Bandung", "bandung", "Bdg", "BANDUNG"],
    "Surabaya": ["Surabaya", "surabaya", "Sby", " Surabaya "],
    "Semarang": ["Semarang", "semarang", "Smg"],
    "Malang": ["Malang", "malang"],
    "Solo": ["Solo", "Surakarta", "solo"],
    "Bekasi": ["Bekasi", "bekasi"],
    "Medan": ["Medan", "medan"],
    "Makassar": ["Makassar", "makassar", "Ujung Pandang"],
    "Denpasar": ["Denpasar", "denpasar", "Bali"],
}
CITY_WEIGHTS = {"Yogyakarta": 30, "Sleman": 8, "Jakarta": 18, "Bandung": 9, "Surabaya": 8, "Semarang": 6,
                "Malang": 5, "Solo": 5, "Bekasi": 4, "Medan": 3, "Makassar": 2, "Denpasar": 2}
UNKNOWN_CITIES = ["asdf", "-", "Mars", "n/a"]

DRINK_SPELLINGS = {
    "Coffee": ["coffee", "Coffee", "kopi", "Kopi susu", "latte", "americano"],
    "Tea": ["tea", "Teh", "es teh", "Es Teh Manis", "green tea"],
    "Matcha": ["matcha", "Matcha latte"],
    "Boba": ["boba", "Boba", "bubble tea"],
    "Water": ["water", "air putih", "Water"],
}
DEVICE_SPELLINGS = {"Android": ["Android", "android", "ANDROID", "samsung"], "iOS": ["iPhone", "iOS", "ios", "iphone"]}

WORD_NUMBERS = {0: "none", 1: "one", 2: "two", 3: "three", 5: "five", 7: "every day"}


def pick(rng, spellings):
    return rng.choice(spellings)


def render_birthday(rng, d: date) -> str:
    # Slash and dash dates are always day first (Indonesian convention); the cleaning must know that.
    fmt = rng.choices(
        ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d %Y", "%d %B %Y", "%d/%m/%y"],
        weights=[30, 25, 10, 8, 8, 7, 6, 6],
    )[0]
    return d.strftime(fmt)


def render_coffee(rng, cups: int) -> str:
    style = rng.random()
    if style < 0.55:
        return str(cups)
    if style < 0.65:
        return f"{cups} cups"
    if style < 0.73 and cups in WORD_NUMBERS:
        return WORD_NUMBERS[cups]
    if style < 0.82 and cups >= 1:
        return f"{cups - 1}-{cups}"
    if style < 0.86 and cups >= 10:
        return f"{cups}+"
    if style < 0.90:
        return f"{cups},5" if cups < 10 else str(cups)
    return str(cups)


def main() -> None:
    rng = random.Random(SEED)
    start = datetime(2026, 10, 21, 9, 0, 0)
    survey_day = start.date()
    rows = []

    for i in range(STUDENTS):
        student_id = f"S{1000 + i}"
        submitted = start + timedelta(seconds=rng.randint(5, 900))
        city = rng.choices(list(CITY_WEIGHTS), weights=list(CITY_WEIGHTS.values()))[0]
        hometown = pick(rng, CITY_SPELLINGS[city])
        born = date(rng.randint(1999, 2006), rng.randint(1, 12), rng.randint(1, 28))
        birthday = render_birthday(rng, born)
        cups = rng.choices(range(0, 15), weights=[10, 9, 11, 12, 10, 8, 6, 8, 4, 3, 4, 2, 2, 1, 2])[0]
        coffee = render_coffee(rng, cups)
        drink = pick(rng, DRINK_SPELLINGS[rng.choices(list(DRINK_SPELLINGS), weights=[38, 24, 12, 16, 10])[0]])
        device = pick(rng, DEVICE_SPELLINGS[rng.choices(["Android", "iOS"], weights=[62, 38])[0]])

        # Rare problems, each on a few rows.
        roll = rng.random()
        if roll < 0.02:
            birthday = ""                                                    # left blank
        elif roll < 0.035:
            birthday = (survey_day + timedelta(days=rng.randint(30, 900))).isoformat()  # impossible: future
        roll = rng.random()
        if roll < 0.03:
            coffee = rng.choice(["?", "", "idk"])                            # unknown
        elif roll < 0.04:
            coffee = str(rng.choice([30, 40, 50]))                           # outlier
        elif roll < 0.05:
            coffee = str(-rng.randint(1, 5))                                 # impossible: negative
        if rng.random() < 0.015:
            hometown = rng.choice(UNKNOWN_CITIES)                            # not a city
        if rng.random() < 0.03:
            drink = ""

        rows.append([student_id, submitted, hometown, birthday, coffee, drink, device])

    # Resubmissions: same student later. Half are exact double-clicks, half change an answer.
    for original in rng.sample(rows, RESUBMISSIONS):
        again = list(original)
        again[1] = original[1] + timedelta(seconds=rng.randint(20, 600))
        if rng.random() < 0.5:
            again[4] = str(rng.randint(0, 10))                                # corrected coffee answer
        rows.append(again)

    rows.sort(key=lambda r: r[1])
    out = Path(__file__).parent / "bronze" / "class_survey_raw.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["response_id", "submitted_at", "student_id", "hometown", "birthday",
                    "coffee_per_week", "favorite_drink", "device"])
        for n, r in enumerate(rows, start=1):
            w.writerow([f"R{n:04d}", r[1].strftime("%Y-%m-%d %H:%M:%S"), *[r[0]], *r[2:]])
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
