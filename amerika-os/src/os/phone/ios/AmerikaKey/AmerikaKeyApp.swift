import SwiftUI

@main
struct AmerikaKeyApp: App {
    @StateObject private var model = KeyModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .onAppear { UIApplication.shared.isIdleTimerDisabled = true; model.start() }
                .preferredColorScheme(.dark)
        }
    }
}
