using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.JSInterop;
using TimelineZLA.Models;
using TimelineZLA.Services;
using System.Text.Json;

namespace TimelineZLA.Pages
{
    public partial class TimelineEditor
    {
        [Parameter]
        public string JobCode { get; set; } = string.Empty;

        [SupplyParameterFromQuery]
        public string? Role { get; set; }

        // --- Core state ---
        private bool IsHost = true;
        private bool hasReceivedInitialData = false;
        private bool isSyncing = false;
        private bool lobbyIsOpen = false;
        private Job currentJob = new();
        private DotNetObjectReference<TimelineEditor>? dotNetRef;
        private int lastRenderedEntryCount = 0;

        // --- Connection state ---
        private string? pendingHostConnect = null;
        private string connectionStatus = "Connecting to Host...";
        private string? connectionError = null;

        // --- Guest name (feature #4) ---
        private bool showGuestNamePrompt = false;
        private string guestDisplayName = string.Empty;

        // --- Connected guests map (feature #4) ---
        private Dictionary<string, string> connectedGuests = new();

        // --- Entry delete (feature #1) ---
        private string? deleteConfirmEntryId = null;

        // --- Timestamp edit (feature #6) ---
        private string? editingTimestampId = null;

        // --- Saved heartbeat (feature #3) ---
        private DateTime? lastSavedAt = null;
        private Timer? _heartbeatTimer;

        // --- File sharing panel ---
        private List<SharedFile> sharedFiles = new();
        private bool showFilesPanel = false;
        private bool isProcessingFiles = false;
        private string fileStatus = string.Empty;
        private string? savedEntryId = null;

        // --- Feature #1: Entry Tags ---
        private string? tagInputEntryId = null;
        private string newTagValue = string.Empty;

        // --- Feature #2: Search / Filter ---
        private string searchQuery = string.Empty;
        private string typeFilter = string.Empty;
        private bool showSearchBar = false;

        // --- Feature #3: Pin ---
        // IsPinned lives on TimelineEntry model

        // --- Feature #4: Entry type ---
        // EntryType lives on TimelineEntry model

        // --- Feature #5: Job summary ---
        private bool showSummaryPanel = false;

        // --- Feature #7: Theme ---
        private string currentTheme = "dark";
        private string ThemeIcon => currentTheme switch { "light" => "light_mode", "hc" => "contrast", _ => "dark_mode" };

        // --- Feature #8: Duration timer ---
        private Timer? _durationTimer;

        // Computed filtered + sorted entry list
        private IEnumerable<TimelineEntry> FilteredEntries
        {
            get
            {
                var entries = currentJob.Entries.AsEnumerable();
                if (!string.IsNullOrWhiteSpace(searchQuery))
                    entries = entries.Where(e =>
                        StripHtml(e.ContentHtml).Contains(searchQuery, StringComparison.OrdinalIgnoreCase) ||
                        e.Tags.Any(t => t.Contains(searchQuery, StringComparison.OrdinalIgnoreCase)));
                if (!string.IsNullOrWhiteSpace(typeFilter))
                    entries = entries.Where(e => e.EntryType == typeFilter);
                return entries.OrderByDescending(e => e.IsPinned).ThenByDescending(e => e.Timestamp);
            }
        }

        private static string StripHtml(string html)
        {
            if (string.IsNullOrEmpty(html)) return string.Empty;
            return System.Text.RegularExpressions.Regex.Replace(html, "<.*?>", " ");
        }

        protected override void OnInitialized()
        {
            if (!string.IsNullOrEmpty(Role) && Role.ToLower() == "guest")
            {
                IsHost = false;
                showGuestNamePrompt = true; // Show name prompt before connecting
            }

            Sync.OnDataReceived += OnSyncDataReceived;
            Sync.OnConnected += OnPeerConnected;
            Sync.OnDisconnected += OnPeerDisconnected;
            Sync.OnPeerIdGenerated += OnGuestPeerReady;
            Sync.OnRetrying += OnConnectionRetrying;
            Sync.OnError += OnConnectionError;
            dotNetRef = DotNetObjectReference.Create(this);
        }

        protected override async Task OnAfterRenderAsync(bool firstRender)
        {
            if (firstRender)
            {
                if (IsHost)
                {
                    var job = await Storage.GetJobAsync(JobCode);
                    if (job != null) currentJob = job;

                    lobbyIsOpen = true;
                    await Sync.InitializeAsync(JobCode);
                    hasReceivedInitialData = true;

                    // Heartbeat timer — refreshes "Saved X ago" every 15s
                    _heartbeatTimer = new Timer(_ => InvokeAsync(StateHasChanged), null,
                        TimeSpan.FromSeconds(15), TimeSpan.FromSeconds(15));

                    // Feature #8: Duration timer — updates "Xh Ym on site" every 60s
                    _durationTimer = new Timer(_ => InvokeAsync(StateHasChanged), null,
                        TimeSpan.FromSeconds(60), TimeSpan.FromSeconds(60));

                    // Feature #7: Load saved theme
                    currentTheme = await JSRuntime.InvokeAsync<string>("zlaInterop.getTheme");

                    StateHasChanged();
                }
                // Guest: wait for name input
            }

            // Initialize any new editor blocks
            if (currentJob.Entries.Count != lastRenderedEntryCount)
            {
                lastRenderedEntryCount = currentJob.Entries.Count;
                foreach (var entry in currentJob.Entries)
                {
                    await JSRuntime.InvokeVoidAsync("timelineEditor.init", $"zla-editor-{entry.Id}", dotNetRef);
                    if (firstRender && IsHost)
                    {
                        await JSRuntime.InvokeVoidAsync("timelineEditor.setContent", $"zla-editor-{entry.Id}", entry.ContentHtml);
                    }
                }
            }

            // Wire up drag-drop zone whenever the panel is visible
            if (IsHost && showFilesPanel)
            {
                try { await InitDropZone(); } catch { }
            }
        }

        // ─── Feature #4: Guest initiates connection after entering name ───────────
        private async Task StartGuestConnection()
        {
            if (string.IsNullOrWhiteSpace(guestDisplayName)) return;
            showGuestNamePrompt = false;
            connectionStatus = "Connecting to Host...";
            connectionError = null;
            pendingHostConnect = JobCode;
            StateHasChanged();
            await Sync.InitializeAsync();
        }

        private async Task HandleNameKeydown(KeyboardEventArgs e)
        {
            if (e.Key == "Enter") await StartGuestConnection();
        }

        // ─── Lobby toggle ─────────────────────────────────────────────────────────
        private async Task ToggleLobby()
        {
            if (!IsHost) return;
            lobbyIsOpen = !lobbyIsOpen;
            if (lobbyIsOpen)
                await Sync.InitializeAsync(JobCode);
            else
            {
                await Sync.DisconnectAsync();
                isSyncing = false;
                connectedGuests.Clear();
            }
            StateHasChanged();
        }

        // ─── Add entry ────────────────────────────────────────────────────────────
        private async Task AddNewEntry()
        {
            if (!IsHost) return;
            var entry = new TimelineEntry();
            currentJob.Entries.Add(entry);
            currentJob.LastModified = DateTime.UtcNow;
            await Storage.SaveJobAsync(currentJob);
            lastSavedAt = DateTime.Now;
            StateHasChanged();
            if (lobbyIsOpen)
            {
                var payload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }
        }

        // ─── Feature #1: Delete individual entry ──────────────────────────────────
        private void RequestDeleteEntry(string entryId) => deleteConfirmEntryId = entryId;
        private void CancelDeleteEntry() => deleteConfirmEntryId = null;

        private async Task ConfirmDeleteEntry(string entryId)
        {
            currentJob.Entries.RemoveAll(e => e.Id == entryId);
            currentJob.LastModified = DateTime.UtcNow;
            deleteConfirmEntryId = null;
            lastSavedAt = DateTime.Now;
            await Storage.SaveJobAsync(currentJob);
            StateHasChanged();
            if (lobbyIsOpen)
            {
                var payload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }
        }

        // ─── Feature #6: Timestamp override ───────────────────────────────────────
        private void StartEditTimestamp(string entryId)
        {
            if (!IsHost) return;
            editingTimestampId = entryId;
        }

        private void CancelTimestampEdit() => editingTimestampId = null;

        private async Task SaveTimestamp(string entryId, ChangeEventArgs e)
        {
            var entry = currentJob.Entries.FirstOrDefault(x => x.Id == entryId);
            if (entry == null || e.Value == null) return;

            if (DateTime.TryParse(e.Value.ToString(), out var localDt))
            {
                entry.Timestamp = localDt.ToUniversalTime();
                editingTimestampId = null;
                lastSavedAt = DateTime.Now;
                await Storage.SaveJobAsync(currentJob);
                StateHasChanged();
                if (lobbyIsOpen)
                {
                    var payload = new { type = "timeline_update", entries = currentJob.Entries };
                    await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
                }
            }
        }

        // ─── Content save (debounced from JS) ────────────────────────────────────
        [JSInvokable]
        public async Task UpdateContent(string entryId, string html)
        {
            if (!IsHost) return;
            var entry = currentJob.Entries.FirstOrDefault(e => e.Id == entryId);
            if (entry != null && entry.ContentHtml != html)
            {
                isSyncing = true;
                StateHasChanged();

                entry.ContentHtml = html;
                currentJob.LastModified = DateTime.UtcNow;
                await Storage.SaveJobAsync(currentJob);
                lastSavedAt = DateTime.Now;

                if (lobbyIsOpen)
                {
                    var payload = new { type = "timeline_update", entries = currentJob.Entries };
                    await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
                }

                await Task.Delay(500);
                isSyncing = false;
                StateHasChanged();
            }
        }

        private async void HandleBlur(string entryId) => await Task.CompletedTask;

        // ─── Feature #1: Entry Tags ───────────────────────────────────────────────
        private void StartTagInput(string entryId)
        {
            tagInputEntryId = entryId;
            newTagValue = string.Empty;
        }

        private async Task AddTag(string entryId)
        {
            var tag = newTagValue.Trim().ToLower();
            if (string.IsNullOrEmpty(tag)) { tagInputEntryId = null; return; }
            var entry = currentJob.Entries.FirstOrDefault(e => e.Id == entryId);
            if (entry != null && !entry.Tags.Contains(tag))
            {
                entry.Tags.Add(tag);
                await SaveAndBroadcast();
            }
            tagInputEntryId = null;
            newTagValue = string.Empty;
        }

        private async Task RemoveTag(string entryId, string tag)
        {
            var entry = currentJob.Entries.FirstOrDefault(e => e.Id == entryId);
            if (entry != null)
            {
                entry.Tags.Remove(tag);
                await SaveAndBroadcast();
            }
        }

        private async Task HandleTagKeydown(KeyboardEventArgs e, string entryId)
        {
            if (e.Key == "Enter") await AddTag(entryId);
            if (e.Key == "Escape") { tagInputEntryId = null; newTagValue = string.Empty; }
        }

        // ─── Feature #3: Pin/Star ─────────────────────────────────────────────────
        private async Task TogglePin(string entryId)
        {
            var entry = currentJob.Entries.FirstOrDefault(e => e.Id == entryId);
            if (entry == null) return;
            entry.IsPinned = !entry.IsPinned;
            await SaveAndBroadcast();
        }

        // ─── Feature #4: Entry type ───────────────────────────────────────────────
        private async Task SetEntryType(string entryId, string type)
        {
            var entry = currentJob.Entries.FirstOrDefault(e => e.Id == entryId);
            if (entry == null) return;
            entry.EntryType = type;
            await SaveAndBroadcast();
        }

        // ─── Feature #2: Search ───────────────────────────────────────────────────
        private void ToggleSearchBar() { showSearchBar = !showSearchBar; if (!showSearchBar) { searchQuery = string.Empty; typeFilter = string.Empty; } }
        private void ClearSearch() { searchQuery = string.Empty; typeFilter = string.Empty; }
        private void SetTypeFilter(string type) { typeFilter = typeFilter == type ? string.Empty : type; }

        // ─── Feature #5: Job summary ──────────────────────────────────────────────
        private void ToggleSummaryPanel() => showSummaryPanel = !showSummaryPanel;

        private string FormatDuration()
        {
            var start = currentJob.Entries.Any()
                ? currentJob.Entries.Min(e => e.Timestamp)
                : currentJob.CreatedAt;
            var elapsed = DateTime.UtcNow - start;
            if (elapsed.TotalMinutes < 1) return "< 1m";
            if (elapsed.TotalHours < 1) return $"{(int)elapsed.TotalMinutes}m";
            return $"{(int)elapsed.TotalHours}h {elapsed.Minutes}m";
        }

        private Dictionary<string, int> GetEntryTypeCounts() =>
            currentJob.Entries.GroupBy(e => e.EntryType)
                .ToDictionary(g => g.Key, g => g.Count());

        private static string GetTypeEmoji(string type) => type switch
        {
            "photo"     => "📸",
            "alert"     => "⚠️",
            "milestone" => "🏁",
            "check"     => "✅",
            _           => "📝"
        };

        private static string GetTypeLabel(string type) => type switch
        {
            "photo"     => "Photos",
            "alert"     => "Alerts",
            "milestone" => "Milestones",
            "check"     => "Checks",
            _           => "Notes"
        };

        // ─── Feature #7: Theme cycle ───────────────────────────────────────────────
        private async Task CycleTheme()
        {
            currentTheme = currentTheme switch { "dark" => "light", "light" => "hc", _ => "dark" };
            await JSRuntime.InvokeVoidAsync("zlaInterop.setTheme", currentTheme);
            StateHasChanged();
        }

        // ─── Tag chip colors ──────────────────────────────────────────────────────
        private static string GetTagTextColor(string tag)
        {
            var c = new[] { "#2ea043", "#58a6ff", "#f78166", "#d29922", "#a371f7", "#8b949e" };
            return c[Math.Abs(tag.GetHashCode()) % c.Length];
        }
        private static string GetTagBgColor(string tag)
        {
            var c = new[] {
                "rgba(46,160,67,0.15)", "rgba(88,166,255,0.15)", "rgba(247,129,102,0.15)",
                "rgba(210,153,34,0.15)", "rgba(163,113,247,0.15)", "rgba(139,148,158,0.15)"
            };
            return c[Math.Abs(tag.GetHashCode()) % c.Length];
        }

        // ─── Shared save+broadcast helper ─────────────────────────────────────────
        private async Task SaveAndBroadcast()
        {
            currentJob.LastModified = DateTime.UtcNow;
            lastSavedAt = DateTime.Now;
            await Storage.SaveJobAsync(currentJob);
            if (lobbyIsOpen)
            {
                var payload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }
            StateHasChanged();
        }

        // ─── P2P callbacks ────────────────────────────────────────────────────────
        private async void OnPeerConnected(string peerId)
        {
            if (IsHost)
            {
                // Register guest with default name until guest_hello arrives
                connectedGuests[peerId] = "Guest";

                // Feature #7: play chime so host knows someone joined
                try { await JSRuntime.InvokeVoidAsync("zlaInterop.playConnectSound"); } catch { }

                // Push full current state to newly joined guest
                var timelinePayload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(timelinePayload));

                // Also push all currently shared files to the new guest
                foreach (var file in sharedFiles)
                {
                    var filePayload = new
                    {
                        type = "file_share_add",
                        id = file.Id,
                        name = file.Name,
                        mimeType = file.MimeType,
                        base64Data = file.Base64Data,
                        sizeBytes = file.SizeBytes
                    };
                    await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(filePayload));
                }

                await InvokeAsync(StateHasChanged);
            }
            else
            {
                // Guest: introduce ourselves to the host
                var hello = new { type = "guest_hello", name = guestDisplayName };
                await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(hello));
                await InvokeAsync(StateHasChanged);
            }
        }

        private void OnPeerDisconnected(string peerId)
        {
            if (IsHost) connectedGuests.Remove(peerId);
            InvokeAsync(StateHasChanged);
        }

        private async void OnGuestPeerReady(string myPeerId)
        {
            if (!IsHost && pendingHostConnect != null)
            {
                var targetCode = pendingHostConnect;
                pendingHostConnect = null;
                connectionStatus = "Connecting to Host...";
                connectionError = null;
                StateHasChanged();
                await Sync.ConnectToPeerAsync(targetCode);
            }
        }

        private void OnConnectionRetrying(int attempt, int max)
        {
            connectionStatus = $"Host not reachable. Retrying ({attempt}/{max})...";
            connectionError = null;
            InvokeAsync(StateHasChanged);
        }

        private void OnConnectionError(string error)
        {
            connectionError = error;
            InvokeAsync(StateHasChanged);
        }

        private async void OnSyncDataReceived(string peerId, string dataStr)
        {
            try
            {
                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var document = JsonDocument.Parse(dataStr);
                var type = document.RootElement.GetProperty("type").GetString();

                // ── Messages the HOST handles (from guests) ──
                if (IsHost)
                {
                    if (type == "guest_hello")
                    {
                        var name = document.RootElement.GetProperty("name").GetString() ?? "Guest";
                        connectedGuests[peerId] = string.IsNullOrWhiteSpace(name) ? "Guest" : name;
                        await InvokeAsync(StateHasChanged);
                    }
                    return;
                }

                // ── Messages GUESTS handle (from host) ──
                if (type == "timeline_update")
                {
                    isSyncing = true;
                    hasReceivedInitialData = true;
                    StateHasChanged();

                    var updatedEntries = JsonSerializer.Deserialize<List<TimelineEntry>>(
                        document.RootElement.GetProperty("entries").GetRawText(), options);

                    if (updatedEntries != null)
                    {
                        currentJob.JobId = JobCode;
                        currentJob.Entries = updatedEntries;
                        currentJob.LastModified = DateTime.UtcNow;
                        await Storage.SaveJobAsync(currentJob);

                        StateHasChanged();
                        await Task.Delay(50);

                        foreach (var entry in currentJob.Entries)
                        {
                            await JSRuntime.InvokeVoidAsync("timelineEditor.setContent",
                                $"zla-editor-{entry.Id}", entry.ContentHtml);
                        }
                    }

                    await Task.Delay(300);
                    isSyncing = false;
                    StateHasChanged();
                }
                else if (type == "file_share_add")
                {
                    // Guest receives a new shared file from the host
                    var file = new SharedFile
                    {
                        Id          = document.RootElement.GetProperty("id").GetString() ?? Guid.NewGuid().ToString(),
                        Name        = document.RootElement.GetProperty("name").GetString() ?? "file",
                        MimeType    = document.RootElement.GetProperty("mimeType").GetString() ?? "application/octet-stream",
                        Base64Data  = document.RootElement.GetProperty("base64Data").GetString() ?? string.Empty,
                        SizeBytes   = document.RootElement.GetProperty("sizeBytes").GetInt64()
                    };
                    if (!sharedFiles.Any(f => f.Id == file.Id))
                    {
                        sharedFiles.Add(file);
                        showFilesPanel = true;
                    }
                    await InvokeAsync(StateHasChanged);
                }
                else if (type == "file_share_remove")
                {
                    var fileId = document.RootElement.GetProperty("fileId").GetString();
                    sharedFiles.RemoveAll(f => f.Id == fileId);
                    await InvokeAsync(StateHasChanged);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error parsing sync data: " + ex.Message);
            }
        }

        // ─── Retry connection ─────────────────────────────────────────────────────
        // ─── Explicit Save Entry button ───────────────────────────────────────────
        private async Task SaveEntry(string entryId)
        {
            var html = await JSRuntime.InvokeAsync<string>("timelineEditor.getContent", $"zla-editor-{entryId}");
            await UpdateContent(entryId, html);
            savedEntryId = entryId;
            StateHasChanged();
            await Task.Delay(1800);
            savedEntryId = null;
            StateHasChanged();
        }

        // ─── File sharing panel — host picks files ────────────────────────────────
        private void ToggleFilesPanel() => showFilesPanel = !showFilesPanel;

        private async Task OpenFilePicker()
        {
            await JSRuntime.InvokeVoidAsync("zlaFileShare.openPicker", dotNetRef, "files");
        }

        private async Task OpenFolderPicker()
        {
            await JSRuntime.InvokeVoidAsync("zlaFileShare.openPicker", dotNetRef, "folder");
        }

        private async Task InitDropZone()
        {
            await JSRuntime.InvokeVoidAsync("zlaFileShare.initDropZone", "file-drop-zone", dotNetRef);
        }

        // Called by JS after file picker processing starts
        [JSInvokable]
        public void OnFileShareStart(int total)
        {
            isProcessingFiles = true;
            fileStatus = $"Processing 0 / {total}...";
            InvokeAsync(StateHasChanged);
        }

        // Called by JS as each file completes
        [JSInvokable]
        public void OnFileShareProgress(int done, int total, string fileName)
        {
            fileStatus = $"Processing {done} / {total}: {fileName}";
            InvokeAsync(StateHasChanged);
        }

        // Called by JS for each successfully processed file
        [JSInvokable]
        public async Task OnFileShareReceived(string name, string mimeType, string base64Data, long sizeBytes)
        {
            var file = new SharedFile
            {
                Name = name,
                MimeType = mimeType,
                Base64Data = base64Data,
                SizeBytes = sizeBytes
            };
            sharedFiles.Add(file);

            // Broadcast to all connected guests
            if (lobbyIsOpen)
            {
                var payload = new
                {
                    type = "file_share_add",
                    id = file.Id,
                    name = file.Name,
                    mimeType = file.MimeType,
                    base64Data = file.Base64Data,
                    sizeBytes = file.SizeBytes
                };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }

            await InvokeAsync(StateHasChanged);
        }

        // Called by JS if a file was skipped (too large)
        [JSInvokable]
        public void OnFileShareSkipped(string name, string reason)
        {
            fileStatus = $"Skipped '{name}': {reason}";
            InvokeAsync(StateHasChanged);
        }

        // Called by JS when all files are done
        [JSInvokable]
        public void OnFileShareDone()
        {
            isProcessingFiles = false;
            fileStatus = string.Empty;
            showFilesPanel = true;
            InvokeAsync(StateHasChanged);
        }

        // Host removes a file from the shared list
        private async Task RemoveSharedFile(string fileId)
        {
            sharedFiles.RemoveAll(f => f.Id == fileId);
            if (lobbyIsOpen)
            {
                var payload = new { type = "file_share_remove", fileId };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }
            StateHasChanged();
        }

        // Guest (or host) downloads a file locally
        private async Task DownloadSharedFile(SharedFile file)
        {
            await JSRuntime.InvokeVoidAsync("zlaFileShare.downloadFile",
                file.Name, file.MimeType, file.Base64Data);
        }

        private async Task RetryConnection()
        {
            if (IsHost) return;
            connectionError = null;
            connectionStatus = "Reconnecting...";
            StateHasChanged();
            pendingHostConnect = JobCode;
            await Sync.InitializeAsync();
        }

        // ─── Feature #3: Saved heartbeat display ──────────────────────────────────
        private string FormatSavedTime()
        {
            if (lastSavedAt == null) return "Live";
            var elapsed = DateTime.Now - lastSavedAt.Value;
            if (elapsed.TotalSeconds < 15) return "Saved just now";
            if (elapsed.TotalSeconds < 60) return $"Saved {(int)elapsed.TotalSeconds}s ago";
            if (elapsed.TotalMinutes < 60) return $"Saved {(int)elapsed.TotalMinutes}m ago";
            return "Saved";
        }

        // ─── Feature #4: Guest initials helper ───────────────────────────────────
        private static string GetInitials(string name)
        {
            var parts = name.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0) return "?";
            if (parts.Length == 1) return parts[0][..Math.Min(2, parts[0].Length)].ToUpper();
            return $"{parts[0][0]}{parts[^1][0]}".ToUpper();
        }

        // ─── Navigation & export ─────────────────────────────────────────────────
        private void GoHome() => Navigation.NavigateTo("/");

        private async Task ExportPdf()
        {
            string filename = $"TimelineZLA_{JobCode}_{DateTime.Now:yyyyMMdd}.pdf";
            await JSRuntime.InvokeVoidAsync("pdfExport.exportElement", "timeline-export-root", filename);
        }

        private async Task ShareJobCode()
        {
            await JSRuntime.InvokeVoidAsync("zlaInterop.shareJobCode", JobCode);
        }

        // ─── Dispose ──────────────────────────────────────────────────────────────
        public void Dispose()
        {
            _heartbeatTimer?.Dispose();
            _durationTimer?.Dispose();
            Sync.OnDataReceived -= OnSyncDataReceived;
            Sync.OnConnected -= OnPeerConnected;
            Sync.OnDisconnected -= OnPeerDisconnected;
            Sync.OnPeerIdGenerated -= OnGuestPeerReady;
            Sync.OnRetrying -= OnConnectionRetrying;
            Sync.OnError -= OnConnectionError;
            dotNetRef?.Dispose();
        }
    }
}
