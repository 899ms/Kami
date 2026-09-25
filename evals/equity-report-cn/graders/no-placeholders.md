---
type: regex
target: {source: file, path: "report.html"}
match: not_contains
pattern: '>[^<]*\{\{[^}\n]{1,60}\}\}'
---
