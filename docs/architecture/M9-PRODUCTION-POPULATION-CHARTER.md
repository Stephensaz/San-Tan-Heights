# Milestone 9 — Production Population & Community Activation

Status: FROZEN

## Objective

Activate the certified San Tan Heights platform on the complete governed production property corpus without changing the accepted intelligence, governance, security, publication, or presentation semantics from Milestones 1–8.

Milestone 9 is a population and activation milestone, not a feature-design milestone.

## Boundary

M9 owns:

- freezing the production corpus manifest;
- admitting each property through canonical identity, phase, spatial, lineage, and QA eligibility checks;
- populating approved historical and current intelligence inputs;
- materializing Evidence Passports and governed Production Findings;
- generating Agent, Seller, and Public report artifacts through the accepted M8 presentation stack;
- quarantining unresolved or ineligible records;
- proving full-corpus accounting;
- activating publication through controlled cohorts;
- replaying refresh, regeneration, rollback, and exception recovery;
- issuing the final Production Activation Certification decision.

M9 does not own:

- new property-intelligence methods;
- new pricing/value models;
- new identity or phase inference rules;
- new publication tiers;
- new audience rules;
- new presentation capabilities;
- redesign of accepted M1–M8 contracts.

Any defect in those areas is repaired in its owning upstream milestone and then M9 is rerun.

## Production corpus rule

The exact property count is not hard-coded into M9.

The source of truth is the frozen production corpus manifest created in M9-001. Every corpus member must be accounted for as one of:

- ADMITTED
- QUARANTINED
- EXCLUDED_WITH_GOVERNED_REASON

No property may disappear from accounting.

## Ticket sequence

1. M9-001 — Production Corpus Manifest & Admission Bootstrap
2. M9-002 — Canonical Property Roster Population
3. M9-003 — Identity / Phase / Spatial Binding
4. M9-004 — Historical Intelligence Population
5. M9-005 — Current Market & Builder Context Population
6. M9-006 — Evidence Passport & Production Finding Materialization
7. M9-007 — Agent / Seller / Public Report Materialization
8. M9-008 — Exception Quarantine & Repair Workflow
9. M9-009 — Full-Corpus QA & Coverage Audit
10. M9-010 — Controlled Publication Cohorts
11. M9-011 — Refresh / Regeneration / Rollback Replay
12. M9-012 — Production Activation Certification

## Milestone acceptance

M9 may be marked ACCEPTED only when:

- every production corpus member is accounted for;
- zero exceptions remain unclassified;
- zero unauthorized publications exist;
- zero audience-tier leaks exist;
- every published record has complete governed lineage;
- unchanged records remain fingerprint-stable during replay;
- changed records regenerate only from governed dependency changes;
- refresh replay passes;
- rollback replay passes;
- full-corpus certification passes;
- open defects are zero;
- waivers are zero;
- final verdict is PASS / GO.

Conditional GO is prohibited.

## First production action

The next engineering ticket is:

> **M9-001 — Production Corpus Manifest & Admission Bootstrap**

M9-001 must freeze the exact corpus membership, source snapshot references, admission states, quarantine reasons, accounting rules, and deterministic manifest fingerprint before any real production property is populated.
