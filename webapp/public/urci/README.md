# URCI reference images

Any image you drop into this folder with one of the filenames below will
show up automatically at the bottom of the **Final URCI** form. Files
served as static assets by Next.js — no rebuild, no code changes.

## Filenames the form looks for

| Filename | Shown as |
|---|---|
| `deduct_rut.png`         | Rut — deduct chart            |
| `deduct_crown.png`       | Crown — deduct chart          |
| `deduct_corrugation.png` | Corrugation — deduct chart    |
| `deduct_dust.png`        | Dust — deduct chart           |
| `deduct_pothole.png`     | Pothole — deduct chart        |
| `cdv_curve.png`          | Corrected deduct value (CDV)  |
| `severity_classes.png`   | Severity classification key   |

Any filename in the list that's *missing* is silently hidden. Any filename
*not* in the list is ignored (the browser can't enumerate the folder).

If you need another slot, add its filename + caption to the `IMAGES`
array in `webapp/app/components/DistressForms/final_urci.tsx`.

Accepted formats: `.png` or `.jpg`. Suggested max size ~600 KB each to
keep the page snappy.
