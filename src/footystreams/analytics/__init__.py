"""Read-only analytics over an event log: recompute the summary's maps, totals and heatmaps.

May import: domain, events. Nothing here simulates or writes; everything is a pure function of
events (and so of a stored match), which is why the numbers can be checked against the
`match_summary` they came from. Design: docs/design/08-roadmap.md section 1.
"""
