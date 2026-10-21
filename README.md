# Practice: bronze, silver, gold (15 minutes)

Turn 300 raw survey answers into trusted tables and one business answer.
Write **one Python script, `pipeline.py`**, that reads bronze and writes silver and gold.
AI tools and search are allowed.

```text
bronze/class_survey_raw.csv   given, do not edit
silver/                       pipeline.py writes here
gold/                         pipeline.py writes here
pipeline.py                   you write this
```

Run it with:

```bash
python3 pipeline.py
```

## Tasks

| Time | Layer | Create |
|---|---|---|
| 0-2 min | Bronze | Nothing. Open the file: how many rows, how many students? |
| 2-11 min | Silver | `silver/survey_response.csv` and `silver/survey_rejected.csv` |
| 11-15 min | Gold | `gold/students_by_region.csv` |

**`silver/survey_response.csv`**: one row per student. Clean, typed columns, plus
`_loaded_at` (when you wrote it) and `_source_file` (where it came from).

**`silver/survey_rejected.csv`**: rows you refuse, with their raw values and a `reject_reason`.
Never drop a row silently.

**`gold/students_by_region.csv`**: students per city and province, with share of class (%).

## Rules

1. One script does it all: `python3 pipeline.py` rebuilds silver and gold from bronze. Running it twice gives the same rows (only `_loaded_at` changes).
2. Write down every decision you make, as comments in `pipeline.py`. A table is only trusted if its rules are written.
3. Done means you can explain where every bronze row went:
   **bronze rows = silver rows + rejected rows + duplicates removed.**

## Go further

- `silver/ref_city.csv`: city, province, island
- `gold/coffee_by_city.csv`: average and median cups per week, per city
- `gold/drink_preference_by_age_group.csv`: favourite drink share within each age group
