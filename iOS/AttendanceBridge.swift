import UIKit
import WebKit
import ActivityKit

class AttendanceViewController: UIViewController, WKScriptMessageHandler {
    var webView: WKWebView!
    let sharedDefaults = UserDefaults(suiteName: "group.com.timecalc") // Shared App Group sandbox
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupWebView()
    }
    
    private func setupWebView() {
        let contentController = WKUserContentController()
        // Register the message handler name "attendanceBridge"
        contentController.add(self, name: "attendanceBridge")
        
        let config = WKWebViewConfiguration()
        config.userContentController = contentController
        
        webView = WKWebView(frame: self.view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        self.view.addSubview(webView)
        
        // Load PWA url
        if let url = URL(string: "https://timecalc.pages.dev/time-calc") {
            let request = URLRequest(url: url)
            webView.load(request)
        }
    }
    
    // JS Interop Bridge Callback: WKScriptMessageHandler
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "attendanceBridge",
              let payload = message.body as? [String: Any],
              let status = payload["status"] as? String, // "In" or "Out"
              let timestampMs = payload["timestamp"] as? Double else {
            return
        }
        
        let isClockedIn = (status == "In")
        let date = Date(timeIntervalSince1970: timestampMs / 1000.0)
        
        // Write status and timestamp to shared AppGroup sandbox for the Widget to access
        sharedDefaults?.set(isClockedIn, forKey: "isClockedIn")
        sharedDefaults?.set(date, forKey: "lastStatusTime")
        sharedDefaults?.synchronize()
        
        // Control ActivityKit Live Activity
        if isClockedIn {
            LiveActivityManager.shared.startLiveActivity(startTime: date)
        } else {
            LiveActivityManager.shared.stopLiveActivity()
        }
    }
    
    // Public Swift method to trigger clock toggles from Widget App Intents
    func triggerWidgetToggle() {
        DispatchQueue.main.async {
            self.webView.evaluateJavaScript("window.iosPwa.onWidgetToggle();") { (result, error) in
                if let error = error {
                    print("Error calling JS window.iosPwa.onWidgetToggle: \(error.localizedDescription)")
                }
            }
        }
    }
}
