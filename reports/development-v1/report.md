# Run a557da1a-c6f9-4ee8-9fef-67375139cfdc

split `development` · agent `v1` · model `gpt-4.1-mini` · prompt sha256 `0a09474cf5a361533e24972fbd44bde543298ebb190e6e5f839774429ee29ec0`

## Counts

| answers | ok | errors | predicted claims | gold claims | matched | correct |
|---|---|---|---|---|---|---|
| 40 | 36 | 4 | 337 | 376 | 336 | 323 |

Answer errors by type: {'invalid_output': 4}

## Metrics (joint F1 is the headline)

|  | precision | recall | f1 |
|---|---|---|---|
| extraction | 0.997 | 0.8936 | 0.9425 |
| joint | 0.9585 | 0.859 | 0.906 |

Coverage (correct / gold): 0.859 · answer errors: 4

## Diagnostics

- missed_answer_errored (39): A03:335:505, A03:506:687, A03:689:861, A03:862:1043, A03:1240:1409, A03:1410:1563, A03:1564:1742, A03:1744:1917, A03:1918:2069, A04:324:493, A04:494:694, A04:696:899, A04:900:1097, A04:1098:1267, A04:1464:1636, A04:1637:1798, A04:1800:1983, A04:1984:2165, A04:2166:2361, A04:2363:2540, A05:371:531, A05:532:697, A05:699:890, A05:891:1095, A05:1292:1467, A05:1468:1651, A05:1652:1828, A05:1830:1980, A17:335:506, A17:507:694, A17:696:879, A17:880:1054, A17:1055:1247, A17:1444:1607, A17:1608:1785, A17:1787:1932, A17:1933:2114, A17:2115:2336, A17:2338:2519
- missed_not_extracted (1): A18:491:661
- unmatched_boundary_error (0): none
- unmatched_over_extraction (1): A07:885:986
- wrong_label (13): A06:1432:1621 (expected unknown, got supported), A09:492:655 (expected contradicted, got supported), A12:516:674 (expected supported, got unknown), A12:872:1032 (expected contradicted, got supported), A16:455:618 (expected contradicted, got supported), A16:1423:1613 (expected unknown, got supported), A22:1398:1552 (expected supported, got contradicted), A33:1028:1203 (expected supported, got contradicted), A34:809:958 (expected supported, got contradicted), A34:1155:1315 (expected contradicted, got supported), A37:371:556 (expected supported, got contradicted), A37:2218:2407 (expected unknown, got contradicted), A39:2173:2360 (expected unknown, got contradicted)

### Confusion matrix (rows expected)

| expected \ predicted | supported | contradicted | unknown | missed |
|---|---|---|---|---|
| supported | 103 | 4 | 1 | 12 |
| contradicted | 4 | 102 | 0 | 14 |
| unknown | 2 | 2 | 118 | 14 |

### Per difficulty tag

| tag | gold | correct | missed | wrong label |
|---|---|---|---|---|
| arithmetic | 33 | 24 | 4 | 5 |
| box_scope | 9 | 8 | 1 | 0 |
| capability_vs_connector | 12 | 11 | 1 | 0 |
| capability_vs_rating | 4 | 3 | 1 | 0 |
| comparison | 20 | 14 | 2 | 4 |
| condition_scope | 13 | 8 | 1 | 4 |
| condition_swap | 6 | 6 | 0 | 0 |
| conditions | 5 | 3 | 1 | 1 |
| cross_brand_comparison | 2 | 2 | 0 | 0 |
| date_scope | 21 | 19 | 2 | 0 |
| explicit_false | 27 | 23 | 3 | 1 |
| feature_conflation | 23 | 22 | 1 | 0 |
| feature_scope | 6 | 5 | 0 | 1 |
| future_scope | 11 | 10 | 1 | 0 |
| historical_scope | 15 | 14 | 1 | 0 |
| inference | 22 | 20 | 2 | 0 |
| missing_condition | 7 | 5 | 2 | 0 |
| missing_fact | 25 | 23 | 2 | 0 |
| model_scope | 29 | 24 | 5 | 0 |
| negation | 43 | 41 | 2 | 0 |
| negative_missing_fact | 6 | 6 | 0 | 0 |
| outdated_fact | 6 | 4 | 2 | 0 |
| policy_scope | 52 | 49 | 3 | 0 |
| policy_vs_capability | 17 | 15 | 2 | 0 |
| price | 13 | 12 | 1 | 0 |
| price_vs_shipping | 11 | 9 | 2 | 0 |
| qualification | 24 | 22 | 2 | 0 |
| region_scope | 4 | 3 | 1 | 0 |
| requirement_vs_availability | 6 | 4 | 1 | 1 |
| scope | 12 | 9 | 3 | 0 |
| unit_conversion | 32 | 25 | 5 | 2 |
| variant_transfer | 8 | 7 | 1 | 0 |
