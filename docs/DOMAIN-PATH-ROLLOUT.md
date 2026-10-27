# VigilTech path rollout — October 27, 2026

The owner requested the live vigiltech.org domain throughout the sites and explicitly chose paths instead of subdomains. This is additive browser access to the existing services and databases.

| Public address | Existing service |
| --- | --- |
| `/` | Company homepage |
| `/desktop` | Workspace launcher |
| `/social` | Existing Social frontend and `/api` |
| `/search/` | Existing Search gateway |
| `/office/` | Office portal; signed file/save URLs retain their exact document IDs |
| `/drive/` | Existing Nextcloud storage, conditional proxy webroot |
| `/journal/` | Existing Journal, scoped offline cache and MCP URLs |
| `/mail/` | Existing encrypted Mail/Calendar portal and Tuta client |
| `/calendar` | Redirect to `/mail/calendar` |
| `/studio/` | Existing Game Producer, including streamed events |
| `/downloads`, `/icons-wallpapers` | Existing company catalogues |

Legacy origins stay reachable. No PDS hostname, DID, database, profile directory, native identifier, update feed, download filename or secret is changed. The established OIDC issuer remains on the old origin; only exact Drive and Mail callback URLs are added. Accounts can sign in again on the new browser origin; cookies and local-only browser journals are not silently transferred between origins. Users with an unsynced journal on the old origin should export it there and import it on the new origin, or sync with the same account first.

The gateway accepts only fixed upstreams and configured app cookies, rejects foreign Origin headers, streams binary downloads/events unchanged, scopes app cookies, and suppresses Clear-Site-Data so Mail logout cannot clear other apps. Nextcloud `__Host-` SameSite marker cookies retain the protocol-required root path; credentials are still filtered before upstream forwarding.

Deploy app base-path support before the hub switch. Office PUBLIC_ORIGIN becomes https://vigiltech.org/office; Journal https://vigiltech.org/journal; Mail https://vigiltech.org/mail. Their PUBLIC_BASE_PATH values are /office, /journal and /mail. Preserve legacy Office browser aliases. Game Producer uses /studio in hosted mode only. Drive activates /drive only for gateway requests; direct WebDAV and existing OIDC discovery stay unchanged.

Rollback: reconnect each service to its prior pinned commit and restore changed nonsecret URL/base-path variables, then reconnect the hub to afc38e2e83bd6a905bc7e703d163090258f0e28a. Volumes, secrets and data stay in place. Prior commits: Office bdfe3e40d59a30a65e030a03cc799f909bf7c5b2; Drive bfee492624ad318e2b7c6046d08a3061d4d8b5b9; Mail 2a6270155b31b7d0b9eeb86a104e7ef190b71fd1. Journal/Studio deployment IDs are recorded in the takeover status before changing them.
