import Foundation
import Vision

// Verify the app reached its usable guest interface, not just a live process.
let screenshot = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
try VNImageRequestHandler(url: screenshot).perform([request])
let text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n").lowercased()
let signIn = text.range(of: "sign\\s*in", options: .regularExpression) != nil
let friends = text.contains("friends")
let bootstrapError = ["keychainexception", "functioncallexception", "getvaluewithkeyasync"].contains { text.contains($0) }
guard signIn && friends && !bootstrapError else {
    fputs("The simulator did not reach the usable sign-in/feed interface. Inspect the screenshot.\n", stderr)
    exit(1)
}
print("Native guest interface verified: sign-in and Friends controls are visible.")
