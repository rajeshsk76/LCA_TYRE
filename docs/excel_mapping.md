# Excel Mapping

The Excel workbook mapping page reads an uploaded `.xlsx` workbook and performs three steps:

1. Detect workbook sheets.
2. Extract label-value candidates from each sheet.
3. Map recognised labels into `TyreLCAParams`.

The first mapping method is intentionally transparent and conservative. It scans labels and nearby numeric cells, then shows the source sheet, source label, source cell and mapped model field.

Mapped values must be reviewed before use in external LCA claims.
