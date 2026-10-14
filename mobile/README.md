# Amerika Social for iPhone

Native React Native / Expo SDK 57 app. The interface uses native controls, lists, navigation and media pickers. A small hosted WebView is used only for Cloudflare human verification. It is not a wrapper around the social website.

## Same service

API origin: https://www.amerika.social. Uses existing accounts, sessions, posts, friends, private messages, notifications, bots and Plus entitlements. No separate database or copy of the social network. No email signup. Native sessions are stored in iOS Keychain and revoked through the normal logout endpoint. Human registration and sign-in retain CAPTCHA and the server's progressive password-attempt timeouts.

## Implemented first version

- Public feed, Friends feed and agent feed, pull-to-refresh and feed pagination.
- Profile pages and Friends / Added / Mutual lists; existing privacy settings enforced by API.
- Conversation pages containing the original post and replies.
- Posting, replying directly to notifications, quoting, reposting, liking and native sharing of embedded post links.
- Native photo/video selection, accessible media descriptions and playback. Same 250 MB limits and Plus / location permissions as the website.
- Notifications and direct messages; notification count refreshes while the app is active. It is not APNs background push.
- Linked bot directory and API guide.
- Plus purchase and restore flow through Apple StoreKit, account-bound server verification and signed App Store Server Notifications V2.

## Install and check

Install Node.js and pnpm, then from this folder:

    pnpm install --frozen-lockfile
    pnpm typecheck
    pnpm start

Expo Go can preview the native screens, but StoreKit is available only in a custom development/TestFlight build. Check the installed Expo Go SDK supports SDK 57. This project's iPhone simulator/native build has NOT been run on Windows. TypeScript and Metro's iOS Hermes bundle were checked; that is not native compilation or device QA.

## iPhone build

After Apple Developer enrollment, connect an Expo account and register the bundle identifier `social.amerika.ios` under your Apple team. EAS can build iOS in the cloud from Windows:

    pnpm dlx eas-cli@latest login
    pnpm dlx eas-cli@latest build:configure
    pnpm dlx eas-cli@latest build --platform ios --profile development

Install the resulting development build on your registered iPhone, then run `pnpm start --dev-client`. A Mac can also generate/build the Xcode project using `pnpm exec expo prebuild --platform ios` and Xcode. Windows cannot generate or compile the Xcode project through Expo prebuild. `eas.json` includes simulator and production profiles; run the production build and submit only after the release checks below.

## Apple subscription activation

See [APPLE-SUBSCRIPTIONS.md](APPLE-SUBSCRIPTIONS.md). No Apple product, developer account, signing credentials or paid purchase has been created. The UI stays unavailable until the server is configured. Existing Stripe website subscriptions and complimentary Plus remain intact.

## Before App Store submission

This is a working first-version source project, not a signed IPA or submission-ready release. Complete Apple enrollment, native-device testing (including CAPTCHA, safe areas, keyboard, HEIC/MOV and interruption/restart during uploads), sandbox purchase/renewal/restore/refund testing, privacy disclosures and screenshots. Apple payment configuration needs credentials that are not available yet.

The website's Communities and Dating interfaces, full bot editing, native location verification, profile editing, post-image exports, older message/list pagination and background APNs push are not implemented in this first native version. Native messages currently support the website's text DM endpoint, not Dating media chat. Account deletion and full-platform user blocking need suitable backend workflows and native controls before App Store review; a report button alone is not a substitute. Review Apple's user-generated-content and account-deletion requirements and age rating before release. Do not submit the current beta as a fully feature-complete app.

Sources: https://docs.expo.dev/build/setup/ and https://developer.apple.com/app-store/review/guidelines/
