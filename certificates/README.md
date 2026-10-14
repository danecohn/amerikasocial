# Apple public certificate roots

Downloaded from Apple's certificate authority endpoints over HTTPS:

- https://www.apple.com/certificateauthority/AppleRootCA-G3.cer
- https://www.apple.com/certificateauthority/AppleRootCA-G2.cer

These are public trust anchors, not application secrets. Used by Apple's SignedDataVerifier for App Store signed transaction and notification verification. Private In-App Purchase API keys belong only in Railway Variables.
