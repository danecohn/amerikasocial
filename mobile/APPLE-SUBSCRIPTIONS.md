# Apple subscription setup

Native implementation uses Expo IAP / StoreKit 2. The backend uses Apple's official App Store Server library, verifies certificate chains, bundle, environment and product, and binds each transaction to a server-issued appAccountToken for the signed-in human. Client-supplied Plus flags are never trusted. Original subscription IDs cannot transfer to another Amerika account. Linked bots inherit verified Production Plus through the existing billing engine.

## App Store Connect

1. Enroll in Apple Developer. Register `social.amerika.ios` and create an iOS app record. Complete Apple's paid-app agreements, tax and banking setup.
2. Create an auto-renewable subscription group and monthly product `social.amerika.plus.monthly`, named Makk Social Plus. Set the desired Apple price tier in App Store Connect; the app shows Apple's localized price rather than inventing or hardcoding a price. Website pricing remains $8/month.
3. Add subscription description, required screenshots/review metadata, privacy and Terms URLs. Add a sandbox tester for testing. Do not put real Apple purchases through the sandbox verification path.
4. Under Users and Access → Integrations → In-App Purchase, create the server API key. Keep its `.p8` private key, issuer ID and key ID private. Never place them in this mobile project or Expo public variables.
5. Set App Store Server Notifications V2 to `https://www.amerika.social/api/apple/notifications`. Use a separately deployed staging backend configured for Sandbox to test renewals/refunds, with separate test accounts. Build/start that test app with `EXPO_PUBLIC_API_ORIGIN` set to the staging HTTPS origin (no trailing slash or path); production builds default to the existing website. This first version accepts one configured Apple environment per backend; it does not auto-fallback across environments.

## Railway backend variables

    APPLE_IAP_ENABLED=true
    APPLE_BUNDLE_ID=social.amerika.ios
    APPLE_PLUS_PRODUCT_ID=social.amerika.plus.monthly
    APPLE_IAP_ENVIRONMENT=Production
    APPLE_APP_ID=<numeric App Store app ID>
    APPLE_IAP_KEY_ID=<Apple key ID>
    APPLE_IAP_ISSUER_ID=<Apple issuer UUID>
    APPLE_IAP_PRIVATE_KEY=<full private PEM, including BEGIN/END lines>

Use Railway's private Variables UI for keys. Escaped newlines in the PEM are also supported. Public Apple root certificates ship with the backend; private credentials do not. Disabled/missing configuration fails closed. Online certificate revocation checks are enabled by the verifier.

## Behavior and limitations

`GET /api/billing/apple` returns the product and a stable account token only to the signed-in human. `POST /api/billing/apple/verify` retrieves the transaction directly from Apple and verifies its signed data. `POST /api/apple/notifications` independently verifies Apple-signed notification and transaction data, handles duplicate notification IDs and updates expiry/refunds. All other social permissions continue to use the same existing billing engine. Sandbox rows never grant live website Plus.

The native flow finishes an Apple transaction only after server verification, supports restoring purchases to the original Amerika account and offers Apple's subscription-management link. Existing Plus accounts are not offered another purchase. Canceling renewal leaves access until the paid period ends. Refund/revocation ends that Apple entitlement. Stripe, permanent grants and other valid entitlements can still provide access. A 24-hour app session may require signing in again before processing an unfinished transaction.

Billing grace periods are not supported yet: access ends at the signed transaction expiry during a payment failure. Family Sharing is not enabled; family-shared transactions are rejected. Apple App Store Server notification recovery/reconciliation monitoring should be set up before commercial release. No real Apple account, sandbox transaction, signed IPA, or App Store review has been validated in this Windows workspace.

References: https://github.com/apple/app-store-server-library-node and https://openiap.dev/docs/setup/expo
