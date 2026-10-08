# ADR 0009: Lead the overview with identity review and source repair

Date: 2026-10-08. Status: accepted for local implementation; release review pending.

## Context

Acquired-agency implementation and data-operations work starts with unresolved identities and missing source fields. A false merge is worse than a missed match. The synthetic demo's shared-identifier benchmark was used during rule development; it is not held-out evidence of accuracy on agency files.

## Decision

Lead the overview with unresolved review pairs, unidentifiable rows, and the next steps to compare evidence or request source repair. Label the engine's person count as candidate identity groups, rather than implying every output is human-confirmed. Keep source-comparison links, the read-only review boundary, synthetic-data limitations, and identifier-masking context visible. Retain all benchmark measurements, tier usage, costs, run timing, and run provenance under a native expandable details section.

## Consequences

The overview prioritizes the reviewer without changing matching semantics, guard rails, immutable outputs, or fixtures. Detailed engineering evidence remains available. The dashboard does not edit source records, apply decisions, or contact source owners.
