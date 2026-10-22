import CryptoKit
import Foundation
import Network
import SwiftUI

/// What the computer is asking for. Shown on screen; nothing is signed until you approve with Face ID.
struct PendingRequest: Identifiable {
    let id = UUID()
    let kind: String          // "auth" or "pair"
    let host, user, service: String
    let ts: Int
    let nonce: String
    let respond: (Bool) -> Void
}

/// Listens on TCP 38400. The computer reaches it through USB (usbmuxd), so nothing is exposed to the network
/// for normal use; the app only answers while it is open on screen.
final class KeyModel: ObservableObject {
    static let port: NWEndpoint.Port = 38400
    @Published var pending: PendingRequest?
    @Published var status = "Starting…"
    @Published var lastResult = ""
    private var listener: NWListener?

    func start() {
        guard listener == nil else { return }
        do {
            let l = try NWListener(using: .tcp, on: Self.port)
            l.newConnectionHandler = { [weak self] c in self?.handle(c) }
            l.stateUpdateHandler = { [weak self] s in
                DispatchQueue.main.async { self?.status = (s == .ready) ? "Ready. Plug into your computer and approve prompts here." : "\(s)" }
            }
            l.start(queue: .global())
            listener = l
        } catch { status = "Could not listen: \(error.localizedDescription)" }
    }

    // MARK: framing: 4-byte big-endian length + JSON
    private func handle(_ c: NWConnection) {
        c.start(queue: .global())
        c.receive(minimumIncompleteLength: 4, maximumLength: 4) { [weak self] head, _, _, _ in
            guard let self, let head, head.count == 4 else { return c.cancel() }
            let n = Int(head.withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }.bigEndian)
            guard n > 0, n <= 64 * 1024 else { return c.cancel() }
            c.receive(minimumIncompleteLength: n, maximumLength: n) { body, _, _, _ in
                guard let body, let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any] else { return c.cancel() }
                self.dispatch(obj, c)
            }
        }
    }

    private func reply(_ c: NWConnection, _ obj: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: obj) else { return c.cancel() }
        var len = UInt32(data.count).bigEndian
        var frame = Data(bytes: &len, count: 4); frame.append(data)
        c.send(content: frame, completion: .contentProcessed { _ in c.cancel() })
    }

    private func dispatch(_ r: [String: Any], _ c: NWConnection) {
        guard (r["v"] as? Int) == 1, let type = r["type"] as? String, let host = r["host"] as? String,
              let user = r["user"] as? String, let ts = r["ts"] as? Int, let nonce = r["nonce"] as? String,
              abs(Int(Date().timeIntervalSince1970) - ts) <= 90 else { return c.cancel() }
        let service = (r["service"] as? String) ?? ""
        guard type == "auth" || type == "pair" else { return c.cancel() }
        DispatchQueue.main.async {
            self.pending?.respond(false)  // a newer request replaces an unanswered one
            self.pending = PendingRequest(kind: type, host: host, user: user, service: service, ts: ts, nonce: nonce) { ok in
                DispatchQueue.main.async { self.pending = nil }
                self.finish(type, ok, host, user, service, ts, nonce, c)
            }
        }
    }

    private func finish(_ type: String, _ ok: Bool, _ host: String, _ user: String, _ service: String, _ ts: Int, _ nonce: String, _ c: NWConnection) {
        guard ok else {
            reply(c, ["type": type == "pair" ? "pair_result" : "auth_result", "approved": false])
            return DispatchQueue.main.async { self.lastResult = "Denied" }
        }
        do {
            if type == "pair" {
                let pub = try KeyStore.publicKeyBase64()
                let msg = ["AMERIKA-PHONE-PAIR-V1", host, user, String(ts), nonce, pub].joined(separator: "\n")
                let sig = try KeyStore.sign(Data(msg.utf8), reason: "Pair with \(host)")
                reply(c, ["type": "pair_result", "approved": true, "pubkey": pub, "sig": sig, "name": UIDevice.current.name])
            } else {
                let msg = ["AMERIKA-PHONE-AUTH-V1", host, user, service, String(ts), nonce].joined(separator: "\n")
                let sig = try KeyStore.sign(Data(msg.utf8), reason: "Approve \(service) for \(user) on \(host)")
                reply(c, ["type": "auth_result", "approved": true, "sig": sig])
            }
            DispatchQueue.main.async { self.lastResult = "Approved" }
        } catch {
            reply(c, ["type": type == "pair" ? "pair_result" : "auth_result", "approved": false])
            DispatchQueue.main.async { self.lastResult = "Face ID failed" }
        }
    }

    /// Short code shown while pairing so you can compare it with the one on the computer.
    func pairingCode(for r: PendingRequest) -> String {
        guard let pub = try? KeyStore.publicKeyBase64(), let raw = Data(base64Encoded: pub) else { return "------" }
        var h = SHA256(); h.update(data: raw); h.update(data: Data(r.nonce.utf8))
        let d = Array(h.finalize())
        let n = (UInt32(d[0]) << 24 | UInt32(d[1]) << 16 | UInt32(d[2]) << 8 | UInt32(d[3])) % 1_000_000
        return String(format: "%06d", n)
    }
}
