## PR 4: Blocking (2026-10-05)

- New `bob-resolve block --enrollment snapshot|derived [--no-shared-ids]` command: builds the candidate pairs worth comparing and prints how many there are, how many true pairs they cover, and the share found by each key.
- Keys: same MBI, email, or phone; same birth date and last-name initial; same surname sound and ZIP3; plus two birth date variant keys so swapped digits or a swapped month and day still meet.
- About 3,450 candidate pairs instead of 7.5 million, and every one of the 2,167 true pairs is found on both enrollment sides, with or without shared ids (measured on synthetic data).
- The twins, Jr and Sr, spouses, and pasted MBI hard cases all reach the comparison step, so later safety rules can rule on them.
