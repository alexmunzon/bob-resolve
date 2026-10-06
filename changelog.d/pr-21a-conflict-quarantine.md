## PR 21a: Hold every disputed link in a conflicting chain (2026-10-06)

- Fixes a false merge. When automatic matches chained Patrick to Pat to Patricia, the cluster check cut only the weakest link and kept the other. With equal scores it picked by record id, so Pat could be merged with the wrong person.
- Now every automatic link on any path between two conflicting records is held for review. No link in the dispute is kept by score or by record id order. Links outside the dispute, such as a record tied only to one end, are still kept.
- New helper `cluster/blocks.py` finds the links on any path between two records (biconnected blocks). The result does not depend on row order or record id names.
- The CLUSTER_CONFLICT review item lists the whole group and every held link. Each held link has one "split" log line. The dashboard explanation and the config comment now describe this.
- A link a person confirmed in review is checked the same way. If it sits between two conflicting records it is held, logged as a split with tier "review", and counted as cut, never as a merge.
- Cost: fewer automatic merges inside conflicting groups. Those links wait for a person instead. The disputed links still score as automatic matches pair by pair; the cluster check is what holds them (stress test: 1 such link per mode, 0 false merges).
