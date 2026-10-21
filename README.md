# Practice: build bronze, silver and gold from a class survey (15 minutes)

```text
lab/
  bronze/class_survey_raw.csv   given: 300 survey answers, typed with no format rules
  silver/                       empty: students write the clean, trusted tables here
  gold/                         empty: students write the answers here
  generate_bronze.py            rebuilds the bronze file (fixed seed, identical every run)
  reference_solution.py         instructor only: fills silver/ and gold/
```

AI tools and search are allowed. Any tool works: Python, SQL (DuckDB), or a spreadsheet.

## The data

`bronze/class_survey_raw.csv`, 300 rows, synthetic (no real people):
`response_id, submitted_at, student_id, hometown, birthday, coffee_per_week, favorite_drink, device`.

## Steps for students

| Min | Layer | Must do | Go further |
|---|---|---|---|
| 0-2 | Bronze | Open the file. Do not edit it. Count rows and students. | |
| 2-11 | Silver | `silver/survey_response.csv`: one row per student, clean typed columns, plus `_loaded_at` and `_source_file`. `silver/survey_rejected.csv`: rows you refuse, with a `reject_reason`. | `silver/dim_city.csv` (city, province, island), `silver/_dq_report.csv` |
| 11-15 | Gold | `gold/students_by_region.csv`: students per city and province, with share of class. | `gold/coffee_by_city.csv`, `gold/drink_preference_by_age_group.csv` |

Rule for every decision: write it down. A silver table is only trusted if its rules are written.

## What makes it real (and why AI cannot finish it alone)

- **Same city, many spellings**: `Jogja`, `YK`, `Yogya`, `Kab. Sleman`, `Jaksel`, `Surakarta`, `Bali`.
  Is Sleman part of Yogyakarta? Is Bali a city?
- **Dates in 8 formats**: `07-06-2003`, `Apr 11 1999`, `28/10/2001`, `22/03/04`. Day or month first?
- **Coffee as text**: `0 cups`, `1-2`, `12+`, `every day`, `idk`, and a `50`.
- **15 students answered twice.** Some double-clicked, some corrected an answer. Which one is true?
- **Impossible rows**: a birthday after the survey, negative coffee, hometown `Mars`.
  Drop them silently, or keep them somewhere?

An AI will pick answers silently. Students must notice each choice, decide, and defend it.

## Reference rules and numbers

`python3 reference_solution.py` (run only after the exercise: it fills the students' folders).
Its rules are written at the top of the file. In short: reject unknown city, future birthday and
negative coffee into quarantine; latest submission per student wins; unparseable values become
blank; coffee over 21 a week is kept but flagged as an outlier and left out of gold statistics.

Its data-quality report:

| Metric | Value |
|---|---|
| Bronze rows | 300 |
| Rejected (city unknown 4, birthday in future 2, coffee negative 2) | 8 |
| Duplicates resolved (latest wins) | 15 |
| Silver rows, one per student | 277 |
| Coffee outliers flagged | 1 |
| Blank birthday / coffee / drink | 5 / 7 / 4 |

**Check: 300 = 277 + 8 + 15.** The script fails if this accounting does not add up.

Gold, top of each table:

| Table | Top rows |
|---|---|
| `students_by_region` | Yogyakarta 86 (31.0%), Jakarta 47 (17.0%), Bandung 25 (9.0%) |
| `coffee_by_city` | Yogyakarta: 83 answers, avg 4.32, median 3 |
| `drink_preference_by_age_group` | 20 or under: Tea 31.7%, Coffee 26.8%, Matcha 17.1% |

## Debrief

Collect a few students' silver row counts and top city. They will differ. Ask what they
decided for Sleman, the resubmissions, and the `50` cups. Then show the row-accounting check:
a professional silver layer can explain where every bronze row went.
