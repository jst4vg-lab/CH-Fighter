# Crea collection inventory

Read-only inspection of `Crea/` on 2026-11-21. The importer excludes any folder whose name contains `repost` or `misc`, including `repost-misc` and `repost-uncropped-nonwarr`.

| Measure | Finding |
|---|---:|
| Files under source | 1,014 |
| Excluded | 310 |
| Eligible | 704 |
| Creators | taco 303, oneg 166, lxrd 142, pega 93 |
| Branches | Army 317, Air Corps 160, Naval 94, Space 72, Expeditionary Force 21, Defense 21, Missiles 19 |
| BP-tagged filenames | 30 |
| Exact SHA-256 duplicate groups | 0 |
| Case-insensitive filename collisions | 0 |

The standard stem is `branch-type-creator-#` or `branch-type-creator-Nbp-#`. Two corrected Space Combat filenames use underscores for the first two separators: `hf_sct_oneg-7.png` and `hf_sct_oneg-20.jpg`. The parser accepts both delimiters and retains the originals unchanged. Missiles files live directly in each creator's `Missiles/` folder and all use `mi-mis`.

Folder labels vary by creator (`figher`/`fighter`, `mobilty`/`mobility`, `tanks`/`tank`, etc.), so filename codes are authoritative. `air assault` contains both `aas` and `par` codes; Naval `transport` contains `tsp` and `tsb`. Creator and branch folders were consistent with parsed filenames at inspection time. The inventory has 26 branch/type code pairs.

Content inspection: 444 JPEG and 260 PNG files, despite extensions of 320 `.jpg`, 121 `.jpeg`, and 263 `.png`. Three `.png` names contain JPEG data: `mi-mis-taco-4.png`, `ar-mbt-taco-58.png`, and `ar-mbt-taco-59.png`. All 704 images decoded successfully. There are 533 distinct dimensions, 657 landscape and 47 portrait files. The most common size is 1280×720 (115 files). Ratios range from about 0.274 to 13.736. Four images contain actual transparency. The eligible source totals about 109 MB.

Representative formatting checks should cover a common 1280×720 source, a portrait missile, an ultra-wide Space or Naval image, a BP-tagged image, a transparent PNG, a content/extension mismatch, and both underscore variants. The formatter reads image content rather than trusting extensions.
