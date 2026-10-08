---
id: 0173
date: 2026-10-07
type: added
scope: [league]
milestone: M11
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: true
migration: false
summary: Add contract renewal talks and expiry
---
Players' willingness weighs wage against market wage, club standing against ambition, mood, free-agent status and loyalty; negotiate() runs up to three rounds of rising wage offers scaled to the club's budget. The rollover now runs renewal talks instead of renewing automatically (a failed talk leaves a contract dispute), and ContractExpiryStage frees players whose contract ended the day after the contract-end day.
