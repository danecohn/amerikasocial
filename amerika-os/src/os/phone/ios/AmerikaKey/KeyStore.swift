import CryptoKit
import Foundation
import LocalAuthentication
import Security

/// The signing key lives in the Secure Enclave and can only be used after Face ID / Touch ID.
/// It never leaves the chip; only the public key is shared with the computer.
enum KeyStore {
    private static let tag = "org.amerika.key.p256"

    static func privateKey() throws -> SecureEnclave.P256.Signing.PrivateKey {
        if let blob = loadBlob() { return try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: blob) }
        var error: Unmanaged<CFError>?
        guard let access = SecAccessControlCreateWithFlags(
            nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly, [.privateKeyUsage, .biometryCurrentSet], &error) else {
            throw error!.takeRetainedValue() as Error
        }
        let key = try SecureEnclave.P256.Signing.PrivateKey(accessControl: access)
        storeBlob(key.dataRepresentation)
        return key
    }

    static func publicKeyBase64() throws -> String {
        try privateKey().publicKey.x963Representation.base64EncodedString()
    }

    /// DER-encoded ECDSA P-256 / SHA-256 signature. Triggers the Face ID prompt.
    static func sign(_ message: Data, reason: String) throws -> String {
        let context = LAContext()
        context.localizedReason = reason
        let key = try SecureEnclave.P256.Signing.PrivateKey(
            dataRepresentation: try blobOrCreate(), authenticationContext: context)
        return try key.signature(for: message).derRepresentation.base64EncodedString()
    }

    private static func blobOrCreate() throws -> Data {
        if let blob = loadBlob() { return blob }
        return try privateKey().dataRepresentation
    }

    private static func loadBlob() -> Data? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: tag,
                                    kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: CFTypeRef?
        return SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess ? out as? Data : nil
    }

    private static func storeBlob(_ data: Data) {
        let attrs: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: tag,
                                    kSecValueData as String: data,
                                    kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: tag] as CFDictionary)
        SecItemAdd(attrs as CFDictionary, nil)
    }
}
