# Comparison v1 vs v2 (development)

run A `a557da1a-c6f9-4ee8-9fef-67375139cfdc` · run B `e5b844a9-7dcd-4e18-856e-9d598e04d132`

| metric | v1 | v2 | delta |
|---|---|---|---|
| extraction_precision | 0.997 | 1.0 | 0.003 |
| extraction_recall | 0.8936 | 0.9628 | 0.0692 |
| extraction_f1 | 0.9425 | 0.981 | 0.0385 |
| joint_precision | 0.9585 | 0.9751 | 0.0166 |
| joint_recall | 0.859 | 0.9388 | 0.0798 |
| joint_f1 | 0.906 | 0.9566 | 0.0506 |
| coverage | 0.859 | 0.9388 | 0.0798 |

Answer errors: v1 4, v2 1

## fixed (36)

| claim | expected | v1 | v2 |
|---|---|---|---|
| A04:1098:1267 | supported | missed | supported |
| A04:1464:1636 | supported | missed | supported |
| A04:1637:1798 | contradicted | missed | contradicted |
| A04:1800:1983 | contradicted | missed | contradicted |
| A04:1984:2165 | unknown | missed | unknown |
| A04:2166:2361 | unknown | missed | unknown |
| A04:2363:2540 | contradicted | missed | contradicted |
| A04:324:493 | contradicted | missed | contradicted |
| A04:494:694 | unknown | missed | unknown |
| A04:696:899 | unknown | missed | unknown |
| A04:900:1097 | supported | missed | supported |
| A05:1292:1467 | supported | missed | supported |
| A05:1468:1651 | contradicted | missed | contradicted |
| A05:1652:1828 | unknown | missed | unknown |
| A05:1830:1980 | contradicted | missed | contradicted |
| A05:371:531 | contradicted | missed | contradicted |
| A05:532:697 | supported | missed | supported |
| A05:699:890 | unknown | missed | unknown |
| A05:891:1095 | unknown | missed | unknown |
| A12:516:674 | supported | unknown | supported |
| A17:1055:1247 | unknown | missed | unknown |
| A17:1444:1607 | contradicted | missed | contradicted |
| A17:1608:1785 | unknown | missed | unknown |
| A17:1787:1932 | supported | missed | supported |
| A17:1933:2114 | supported | missed | supported |
| A17:2115:2336 | contradicted | missed | contradicted |
| A17:2338:2519 | unknown | missed | unknown |
| A17:335:506 | contradicted | missed | contradicted |
| A17:507:694 | unknown | missed | unknown |
| A17:696:879 | contradicted | missed | contradicted |
| A17:880:1054 | supported | missed | supported |
| A18:491:661 | unknown | missed | unknown |
| A22:1398:1552 | supported | contradicted | supported |
| A33:1028:1203 | supported | contradicted | supported |
| A34:809:958 | supported | contradicted | supported |
| A37:2218:2407 | unknown | contradicted | unknown |

## regressed (6)

| claim | expected | v1 | v2 |
|---|---|---|---|
| A02:1469:1659 | unknown | unknown | supported |
| A12:676:871 | unknown | unknown | missed |
| A16:620:828 | unknown | unknown | missed |
| A25:306:459 | supported | supported | contradicted |
| A39:1794:1971 | unknown | unknown | missed |
| A39:1972:2172 | unknown | unknown | missed |

## still_wrong (17)


## still_right (317)

