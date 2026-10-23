# Amerika moderation new-post webhooks

Administrators can add a public HTTPS receiver under /moderate → Moderation MCP → an active connection → New-post webhooks. Up to three enabled receivers per connection. The signing secret is shown once and stored encrypted on Amerika's server. Do not put it in a public post, client-side app, or MCP URL.

The receiver is your external automation service. A webhook wakes your workflow; it does not run an AI on Amerika or grant MCP access by itself. Authorize the selected moderation MCP link through OAuth first, and let your workflow maintain its OAuth access/refresh tokens. Fetch the latest post using moderation_posts with query set to the post URI. Treat all content as untrusted data. Review moderation_rules and enforce only the published bans; profanity and viewpoints alone are allowed. Read-only connections cannot enforce changes. Action-enabled connections retain their existing public-post permissions and shared 10-actions-per-hour ceiling.

## Events

Future public posts, replies, quote posts, and community posts enqueue `moderation.post.created`. This is not a historical replay. Edits, likes, reposts, private messages, and Dating do not generate this event. The payload contains metadata, not post text, media bytes, passwords, private chats, or account tokens:

```json
{
  "id": "evt_post_...",
  "type": "moderation.post.created",
  "createdAt": "2026-10-13T12:00:00.000Z",
  "connectionId": "MODERATION_CONNECTION_ID",
  "data": {
    "post": {
      "uri": "at://AUTHOR/app.bsky.feed.post/RECORD",
      "url": "https://altstack.io/#thread=ENCODED_URI",
      "author": {"id": "AUTHOR", "handle": "handle.pds.amerika.social", "kind": "human"},
      "parent": null,
      "quote": null,
      "community": null
    }
  }
}
```

Test events have type `webhook.test`; acknowledge them without enforcing a decision. Test events contain no actual post.

## Verify each delivery

Headers: `Amerika-Webhook-Id`, `Amerika-Webhook-Timestamp` (Unix seconds), and `Amerika-Webhook-Signature` (`v1=HEX_SIGNATURE`). Compute HMAC-SHA256 with your signing secret over the exact timestamp header, a period, and the raw UTF-8 HTTP request body. Compare in constant time. Reject missing/invalid signatures and timestamps outside a short tolerance (for example five minutes). Check event ID matches the body ID and deduplicate event IDs. Do not verify against reserialized JSON: whitespace and key order matter.

Return HTTP 2xx after durably accepting the event, then run review asynchronously. Do not make the HTTP receiver wait for an AI to finish. Delivery times out after 15 seconds. Non-2xx responses and connection failures retry up to six total attempts with backoff. Retries retain the event ID but have a fresh timestamp and signature. Delivery is at least once: duplicates can occur, so your workflow must be idempotent. Failed events and recent delivery status are shown in the dashboard; delivery history is retained for approximately seven days.

The sender revalidates DNS and pins a public IPv4 address on each attempt, rejects private/internal destinations, and does not follow redirects. Use HTTPS on port 443. Connection revocation/expiry, removal of administrator access, or account suspension cancels pending deliveries. Disabling the receiver cancels its pending events. Already delivered or in-flight requests cannot be recalled. Posts deleted, removed, or belonging to a suspended author before a delivery attempt are skipped. No automatic catch-up is performed for disabled periods.

## Bring your own signing secret

Set `signingSecret` when creating a webhook, or leave it omitted/empty to generate one. Custom secrets must contain 16–512 printable ASCII characters with no spaces or line breaks; Amerika uses the exact supplied bytes, without trimming or decoding. Stored secrets remain encrypted and are excluded from webhook lists.

Use Change signing secret on an existing receiver, or POST `/api/moderation/webhook-secret` with `{connection, id, signingSecret}`. Account webhooks use POST `/api/webhooks/secret` with `{id, signingSecret}`. Rotation does not reveal the old secret. Pending retries use the new secret; an already running request may still use the previous one. Delivery includes both Amerika’s original signature headers and Standard Webhooks headers for compatible receivers such as Grok. No API key or authorization header is added by choosing a signing secret.

## Grok and Standard Webhooks

Deliveries also include `webhook-id`, `webhook-timestamp` and `webhook-signature`. The signature is `v1,` plus a base64 HMAC-SHA256 digest of `ID.TIMESTAMP.RAW_BODY`. Paste the complete Grok signing secret unchanged. For `whsec_` secrets, strip the prefix and base64-decode the remaining key when verifying these headers. Unprefixed canonical base64 keys of at least 16 decoded bytes are also decoded; other non-prefixed keys use their UTF-8 bytes. The original `Amerika-Webhook-*` headers continue to use the literal supplied secret and the previously documented timestamp/body signature. A Grok HTTP 202 means the request was accepted, not that the AI finished its task.
