import ActivityKit
import WidgetKit
import SwiftUI

// 1. Define Activity Attributes and Content State
struct AttendanceAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var startTime: Date
    }
}

// 2. Live Activity Manager to start/stop Activities
class LiveActivityManager {
    static let shared = LiveActivityManager()
    private var currentActivity: Activity<AttendanceAttributes>?
    
    private init() {}
    
    func startLiveActivity(startTime: Date) {
        // Stop any existing activity first
        stopLiveActivity()
        
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        
        let attributes = AttendanceAttributes()
        let initialContentState = AttendanceAttributes.ContentState(startTime: startTime)
        let activityContent = ActivityContent(state: initialContentState, staleDate: nil)
        
        do {
            currentActivity = try Activity.request(attributes: attributes, content: activityContent, pushType: nil)
            print("Successfully requested Live Activity: \(currentActivity?.id ?? "none")")
        } catch {
            print("Error requesting Live Activity: \(error.localizedDescription)")
        }
    }
    
    func stopLiveActivity() {
        guard let activity = currentActivity else { return }
        
        Task {
            // Dismiss immediately from lock screen on clock out
            await activity.end(nil, dismissalPolicy: .immediate)
            self.currentActivity = nil
            print("Ended Live Activity immediately.")
        }
    }
}

// 3. SwiftUI Layout for Lock Screen and Dynamic Island
struct AttendanceLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: AttendanceAttributes.self) { context in
            // Lock Screen UI layout
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Time Calc Shift Active")
                        .font(.headline)
                        .foregroundColor(.blue)
                    Text("Clocked in since \(context.state.startTime, style: .time)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
                // Dynamic count up timer
                Text(context.state.startTime, style: .timer)
                    .font(.title2)
                    .bold()
                    .foregroundColor(.blue)
                    .monospacedDigit()
            }
            .padding()
            .activityBackgroundTint(Color.black.opacity(0.8))
            .activitySystemActionForegroundColor(Color.white)
            
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded Region
                DynamicIslandExpandedRegion(.leading) {
                    Label("Active Shift", systemImage: "clock.badge.checkmark")
                        .font(.headline)
                        .foregroundColor(.blue)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.startTime, style: .timer)
                        .font(.title2)
                        .bold()
                        .foregroundColor(.blue)
                        .monospacedDigit()
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("Keep up the great work!")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            } compactLeading: {
                Image(systemName: "clock.fill")
                    .foregroundColor(.blue)
            } compactTrailing: {
                Text(context.state.startTime, style: .timer)
                    .font(.caption2)
                    .foregroundColor(.blue)
                    .monospacedDigit()
            } minimal: {
                Image(systemName: "clock")
                    .foregroundColor(.blue)
            }
        }
    }
}
