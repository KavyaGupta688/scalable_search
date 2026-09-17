# Licence Expiry in the Zero-Copy Architecture

The ingestion system does not own or delete S3/NAS source content. It records
the current three-year licence state; vendor-side access revocation remains
external. Historical audit events belong to the separate audit module.

## Clock

- Starts after a new file completes SHA-256, MIME validation, vendor metadata
  validation, and its catalogue transaction succeeds.
- Uses the same UTC calendar date three years later.
- February 29 maps to February 28 in a non-leap target year.
- `license_subject_id` is `sha256:<digest>`, so moving the file or creating a
  connector cannot reset the original clock.

## Reconciliation

`scripts/run_retention.py` periodically selects active entitlements whose
`expires_at` is due. In dry-run it reports only. Otherwise it changes
`license_entitlements.status` to `expired` and updates Prometheus metrics.

```powershell
docker compose run --rm retention-reconciler python scripts/run_retention.py --once
```

```sql
SELECT license_subject_id, license_start_at, expires_at, status
FROM license_entitlements
ORDER BY expires_at;
```

No lifecycle rule, object tag, Object Lock operation, source deletion, or local
`retention_events` insert is performed. An approved renewal must create a new
entitlement revision; it must not edit the immutable original clock.
