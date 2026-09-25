---
type: regex
target: {source: file, path: "tidewell.html"}
match: not_contains
pattern: '>[^<]*\{\{[^}\n]{1,60}\}\}'
---
