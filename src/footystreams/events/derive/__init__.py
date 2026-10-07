"""Pure derivations over an event log: the match summary and its parts.

The simulator builds the summary with these functions; `verify` and `analytics` recompute it
from the same events with the same code, so a summary can never silently disagree with its log.
"""
