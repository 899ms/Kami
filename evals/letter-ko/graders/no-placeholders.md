---
type: regex
target: {source: file, path: "letter.html"}
match: not_contains
pattern: '>[^<]*\{\{[^}\n]{1,60}\}\}'
---
