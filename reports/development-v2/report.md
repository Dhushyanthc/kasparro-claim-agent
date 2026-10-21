# Run e5b844a9-7dcd-4e18-856e-9d598e04d132

split `development` · agent `v2` · model `gpt-4.1-mini` · prompt sha256 `fd4c9d66cf612285db8e23f2eb1605757740f8fa74a9175fdfe4ff7e732acc17`

## Counts

| answers | ok | errors | predicted claims | gold claims | matched | correct |
|---|---|---|---|---|---|---|
| 40 | 39 | 1 | 362 | 376 | 362 | 353 |

Answer errors by type: {'invalid_output': 1}

## Metrics (joint F1 is the headline)

|  | precision | recall | f1 |
|---|---|---|---|
| extraction | 1.0 | 0.9628 | 0.981 |
| joint | 0.9751 | 0.9388 | 0.9566 |

Coverage (correct / gold): 0.9388 · answer errors: 1

## Diagnostics

- missed_answer_errored (9): A03:335:505, A03:506:687, A03:689:861, A03:862:1043, A03:1240:1409, A03:1410:1563, A03:1564:1742, A03:1744:1917, A03:1918:2069
- missed_not_extracted (5): A12:676:871, A16:620:828, A39:1794:1971, A39:1972:2172, A39:2173:2360
- unmatched_boundary_error (0): none
- unmatched_over_extraction (0): none
- wrong_label (9): A02:1469:1659 (expected unknown, got supported), A06:1432:1621 (expected unknown, got supported), A09:492:655 (expected contradicted, got supported), A12:872:1032 (expected contradicted, got supported), A16:455:618 (expected contradicted, got supported), A16:1423:1613 (expected unknown, got supported), A25:306:459 (expected supported, got contradicted), A34:1155:1315 (expected contradicted, got supported), A37:371:556 (expected supported, got contradicted)

### Confusion matrix (rows expected)

| expected \ predicted | supported | contradicted | unknown | missed |
|---|---|---|---|---|
| supported | 114 | 2 | 0 | 4 |
| contradicted | 4 | 113 | 0 | 3 |
| unknown | 3 | 0 | 126 | 7 |

### Per difficulty tag

| tag | gold | correct | missed | wrong label |
|---|---|---|---|---|
| arithmetic | 33 | 29 | 1 | 3 |
| box_scope | 9 | 9 | 0 | 0 |
| capability_vs_connector | 12 | 12 | 0 | 0 |
| capability_vs_rating | 4 | 3 | 1 | 0 |
| comparison | 20 | 16 | 1 | 3 |
| condition_scope | 13 | 9 | 1 | 3 |
| condition_swap | 6 | 6 | 0 | 0 |
| conditions | 5 | 5 | 0 | 0 |
| cross_brand_comparison | 2 | 2 | 0 | 0 |
| date_scope | 21 | 21 | 0 | 0 |
| explicit_false | 27 | 26 | 1 | 0 |
| feature_conflation | 23 | 23 | 0 | 0 |
| feature_scope | 6 | 6 | 0 | 0 |
| future_scope | 11 | 11 | 0 | 0 |
| historical_scope | 15 | 15 | 0 | 0 |
| inference | 22 | 22 | 0 | 0 |
| missing_condition | 7 | 6 | 1 | 0 |
| missing_fact | 25 | 23 | 2 | 0 |
| model_scope | 29 | 27 | 2 | 0 |
| negation | 43 | 42 | 1 | 0 |
| negative_missing_fact | 6 | 6 | 0 | 0 |
| outdated_fact | 6 | 5 | 1 | 0 |
| policy_scope | 52 | 50 | 2 | 0 |
| policy_vs_capability | 17 | 17 | 0 | 0 |
| price | 13 | 13 | 0 | 0 |
| price_vs_shipping | 11 | 10 | 1 | 0 |
| qualification | 24 | 23 | 1 | 0 |
| region_scope | 4 | 4 | 0 | 0 |
| requirement_vs_availability | 6 | 5 | 0 | 1 |
| scope | 12 | 11 | 1 | 0 |
| unit_conversion | 32 | 29 | 1 | 2 |
| variant_transfer | 8 | 7 | 1 | 0 |
