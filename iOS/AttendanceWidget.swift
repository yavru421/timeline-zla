import WidgetKit
import SwiftUI
import AppIntents

// 1. App Intent for iOS 17+ widget button interaction
struct ToggleAttendanceIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle Attendance Status"
    static var description = IntentDescription("Clocks in or out directly from the Home Screen.")
    
    init() {}
    
    func perform() async throws -> some IntentResult {
        let sharedDefaults = UserDefaults(suiteName: "group.com.timecalc")
        let currentStatus = sharedDefaults?.bool(forKey: "isClockedIn") ?? false
        let newStatus = !currentStatus
        let now = Date()
        
        // Save new status back to AppGroup shared storage
        sharedDefaults?.set(newStatus, forKey: "isClockedIn")
        sharedDefaults?.set(now, forKey: "lastStatusTime")
        sharedDefaults?.synchronize()
        
        // Notify the main WKWebView app wrapper to trigger a web update
        // Using a NotificationCenter trigger, which the main app wrapper listens for
        NotificationCenter.default.post(name: Notification.Name("WidgetDidToggleAttendance"), object: nil, userInfo: ["isClockedIn": newStatus])
        
        // Control Live Activity accordingly from background
        if newStatus {
            LiveActivityManager.shared.startLiveActivity(startTime: now)
        } else {
            LiveActivityManager.shared.stopLiveActivity()
        }
        
        return .result()
    }
}

// 2. Widget Timeline Provider
struct AttendanceProvider: TimelineProvider {
    func placeholder(in context: Context) -> AttendanceEntry {
        AttendanceEntry(date: Date(), isClockedIn: false, lastStatusTime: Date())
    }

    func getSnapshot(in context: Context, completion: @escaping (AttendanceEntry) -> ()) {
        let entry = readCurrentState()
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        let entry = readCurrentState()
        // Never expires, updates are explicitly pushed by AppIntent or WebApp changes
        let timeline = Timeline(entries: [entry], policy: .atEnd)
        completion(timeline)
    }
    
    private func readCurrentState() -> AttendanceEntry {
        let sharedDefaults = UserDefaults(suiteName: "group.com.timecalc")
        let isClockedIn = sharedDefaults?.bool(forKey: "isClockedIn") ?? false
        let lastStatusTime = sharedDefaults?.object(forKey: "lastStatusTime") as? Date ?? Date()
        return AttendanceEntry(date: Date(), isClockedIn: isClockedIn, lastStatusTime: lastStatusTime)
    }
}

// 3. Widget Entry Model
struct AttendanceEntry: TimelineEntry {
    let date: Date
    let isClockedIn: Bool
    let lastStatusTime: Date
}

// 4. Widget SwiftUI View with iOS 17+ Button Intent
struct AttendanceWidgetEntryView : View {
    var entry: AttendanceProvider.Entry

    var body: some View {
        VStack(spacing: 8) {
            Text("Work Shift")
                .font(.caption2)
                .bold()
                .foregroundColor(.secondary)
            
            HStack(spacing: 6) {
                Circle()
                    .fill(entry.isClockedIn ? Color.green : Color.red)
                    .frame(width: 8, height: 8)
                
                Text(entry.isClockedIn ? "Clocked In" : "Clocked Out")
                    .font(.subheadline)
                    .bold()
                    .foregroundColor(entry.isClockedIn ? .green : .red)
            }
            
            // Displays dynamic relative clock time
            Text(entry.lastStatusTime, style: .relative)
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundColor(.gray)
            
            // Interactive button utilizing App Intent (iOS 17+)
            Button(intent: ToggleAttendanceIntent()) {
                Text(entry.isClockedIn ? "Clock Out" : "Clock In")
                    .font(.caption)
                    .bold()
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(entry.isClockedIn ? Color.red : Color.blue)
                    .cornerRadius(8)
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .containerBackground(.black.opacity(0.05), for: .widget)
    }
}

// 5. Widget Configuration Setup
@main
struct AttendanceWidget: Widget {
    let kind: String = "AttendanceWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: AttendanceProvider()) { entry in
            AttendanceWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Attendance Status")
        .description("Clock in/out instantly from the iOS home screen.")
        .supportedFamilies([.systemSmall])
    }
}
