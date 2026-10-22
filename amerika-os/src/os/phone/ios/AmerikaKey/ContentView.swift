import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: KeyModel

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.04, green: 0.04, blue: 0.08), Color(red: 0.10, green: 0.09, blue: 0.19)],
                           startPoint: .top, endPoint: .bottom).ignoresSafeArea()
            VStack(spacing: 22) {
                Text("AMERIKA KEY").font(.system(.title, design: .monospaced).weight(.heavy)).tracking(6)
                    .foregroundColor(.white).shadow(color: .pink.opacity(0.8), radius: 12)
                if let r = model.pending {
                    RequestCard(request: r, code: r.kind == "pair" ? model.pairingCode(for: r) : nil)
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "faceid").font(.system(size: 54)).foregroundColor(.cyan)
                        Text(model.status).multilineTextAlignment(.center).foregroundColor(.gray)
                        if !model.lastResult.isEmpty { Text("Last request: \(model.lastResult)").font(.footnote).foregroundColor(.gray) }
                    }.padding()
                }
                Spacer()
                Text("Keep this app open while your computer asks.").font(.footnote).foregroundColor(.gray)
            }.padding()
        }
    }
}

struct RequestCard: View {
    let request: PendingRequest
    let code: String?

    var body: some View {
        VStack(spacing: 14) {
            Text(request.kind == "pair" ? "Pair with this computer?" : "Approve this request?").font(.headline).foregroundColor(.white)
            VStack(alignment: .leading, spacing: 6) {
                row("Computer", request.host)
                row("User", request.user)
                if request.kind == "auth" { row("For", request.service) }
                if let code { row("Pairing code", code) }
            }
            if request.kind == "pair" {
                Text("Approve only if the same code is shown on the computer.").font(.footnote).foregroundColor(.orange)
            }
            HStack(spacing: 14) {
                Button("Deny") { request.respond(false) }.buttonStyle(.bordered).tint(.gray)
                Button("Approve with Face ID") { request.respond(true) }.buttonStyle(.borderedProminent).tint(.pink)
            }
        }
        .padding(18)
        .background(RoundedRectangle(cornerRadius: 20).fill(Color.white.opacity(0.07)))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color.cyan.opacity(0.5)))
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack { Text(k.uppercased()).font(.caption).foregroundColor(.gray); Spacer()
                 Text(v).font(.system(.body, design: .monospaced)).foregroundColor(.white) }
    }
}
