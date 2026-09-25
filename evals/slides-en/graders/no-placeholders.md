---
type: regex
target: {source: file, path: "deck.html"}
match: not_contains
pattern: '>[^<]*\{\{[^}\n]{1,60}\}\}'
---
