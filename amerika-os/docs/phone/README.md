# Amerika Phone Key

Approve `sudo` and administrator (polkit) prompts with an iPhone: plug it in, open **Amerika Key**, confirm with Face ID.

## How it works
- The iPhone app creates a P-256 key inside the Secure Enclave. It needs Face ID/Touch ID for every signature and never leaves the chip.
- `amerika-phone pair` registers the phone's **public** key for your user in `/etc/amerika/phone-auth/<user>.json`. You compare a 6-digit code shown on both screens.
- When `sudo`/a polkit prompt asks for authentication, a PAM rule (`pam_exec` → `amerika-phone-pam`) sends a random challenge over USB (through `usbmuxd`, TCP port 38400 on the phone). The phone shows host/user/service; after Face ID it signs `AMERIKA-PHONE-AUTH-V1 | host | user | service | time | nonce`. The computer verifies the signature, the time (90 s) and the nonce. An approval can't be reused for another prompt.
- The rule is `sufficient`: if no phone is plugged in, the app isn't open, you deny, or anything fails, the normal password prompt appears. Your password is never removed.

## Scope (deliberately small)
`sudo` and polkit (graphical admin prompts) only. NOT the login screen, the lock screen, SSH or disk encryption: a mistake there can lock you out.

## Install
```
sudo apt install amerika-phone
```
Build the iPhone app (needs a Mac with Xcode and an Apple ID; a free ID signs for 7 days, a paid developer account removes that):
1. Xcode → New Project → iOS → App, product name `AmerikaKey`, interface SwiftUI, language Swift.
2. Replace the generated Swift files with the four files from `/usr/share/amerika-phone/ios/AmerikaKey/`; delete the default `ContentView.swift` first.
3. Add `NSFaceIDUsageDescription` (see `Info-additions.plist.txt`). Select your phone and Run. On the phone: Settings → General → VPN & Device Management → trust your developer profile.

## Use
```
amerika-phone status
amerika-phone pair                 # phone connected over USB, app open and unlocked; compare the 6-digit code
amerika-phone test                 # asks the phone, changes nothing
amerika-phone enable sudo          # then: sudo -k && sudo true   (keep another root shell open the first time)
amerika-phone enable polkit        # optional: graphical admin prompts
```

## Undo
```
amerika-phone disable              # removes the PAM lines (sudo and polkit)
amerika-phone remove <fingerprint> # forget a phone
```
If `sudo` is ever unusable: boot to recovery or use `pkexec`/a root TTY and run `/usr/libexec/amerika/amerika-phone-helper disable`, or restore `/var/lib/amerika-os/phone/sudo.orig` to `/etc/pam.d/sudo`.

## Security notes
- The protocol never carries a secret; the host stores only public keys (root-owned).
- Someone who steals your unlocked phone **and** passes Face ID could approve prompts. A sealed attack needs your face (biometryCurrentSet invalidates the key if enrolled faces change).
- Anyone with root can change the PAM rules, as always.
- Only users with a registered phone get the phone prompt; other users and services are untouched.

## Not verified
The iPhone app has not been compiled or run (no Xcode in the development environment). The Linux side is tested against a simulated phone and the real `usbmuxd` path up to the phone refusing the connection when the app is absent.
