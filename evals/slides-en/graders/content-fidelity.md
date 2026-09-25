---
type: llm
weight: 2
focus: {source: file, path: "deck.html"}
---

PASS only if all of these hold in the filled HTML deck:
- The provided numbers survive unchanged: 400 services/repos, 37 CI configs, 6 weeks, 5 waves, 11 months, 3 days, 41%, 88%, 23 to 9 minutes, 2 days, 12 legacy repos, Q1.
- Most content slide titles are assertions (a full claim such as "Remote caching doubled our hit rate") rather than topic labels ("Results").
- No invented metrics, quotes, or team names.
FAIL if numbers are altered or invented, or if most titles are bare topic labels.
