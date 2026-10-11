# Vietnam Checkout Data Toolkit

Normalize Vietnamese province mentions in customer-entered text and flag inputs that need review.
Use a verified July 2025 government province snapshot, or explicitly select the historical
63-province dataset. Results identify the dataset version and preserve ambiguity.

## Use cases

- Standardize province fields before importing orders into your own system.
- Process up to 50 values per batch while retaining input order.
- Flag unmatched or multiple province mentions for review.
- Check conservative phone, ASCII email and tax-code syntax.

## Quick start

Call `GET /normalize?q=Ha%20Noi` to receive a matched province with code `01`.
Call `POST /normalize/batch` with:

```json
{"queries":["Ha Noi","Long An","Ha Noi, Ho Chi Minh"],"version":"2025"}
```

Expected statuses: `matched`, `not_found`, `ambiguous`.
To look up a province name from the historical dataset, use `version=legacy`.
This is not an automatic conversion from an old address to a merged province.

## Limits

Maximum 50 values per batch, 500 characters per value, 64 KiB request body.
Lookup concerns province names only: no ward/district resolution, geocoding, delivery coverage,
identity checks, tax registry queries, mailbox deliverability or active phone-number verification.
The province data is a dated snapshot; future government changes require a new verified release.
Single-name mentions may refer to streets or businesses, so review flagged inputs and test your
own samples. A successful syntax check does not establish that a person, account or record exists.

## Data sources

The 2025 snapshot was extracted from the Government news portal's published code table:
https://baochinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-3321-don-vi-hanh-chinh-cap-xa-moi-102250704153652947.htm

Historical source: https://provinces.open-api.vn/api/v1/
This service is independently provided, not a government-issued API.

## Privacy and integration

The application does not intentionally persist submitted input. Deploy with access logging
disabled; hosting and RapidAPI may independently retain request logs under their policies.
Send only data you are entitled to process. The backend verifies the RapidAPI proxy secret.
Customers use their RapidAPI subscription credentials; the backend secret is never shared.

## Availability

This document is the prepared listing copy. Publication, live backend URL, hosting availability
and successful RapidAPI import remain to be verified before accepting paid usage.
