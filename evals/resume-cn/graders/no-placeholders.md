---
type: regex
target: {source: file, path: "resume.html"}
match: not_contains
pattern: '>[^<]*\{\{[^}\n]{1,60}\}\}'
---
