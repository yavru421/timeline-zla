using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Components;
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

        private bool IsHost = true;
        private bool hasReceivedInitialData = false;
        private bool isSyncing = false;
        private bool lobbyIsOpen = false;
        private Job currentJob = new();
        private DotNetObjectReference<TimelineEditor>? dotNetRef;
        private int lastRenderedEntryCount = 0;

        protected override void OnInitialized()
        {
            if (!string.IsNullOrEmpty(Role) && Role.ToLower() == "guest")
            {
                IsHost = false;
            }

            Sync.OnDataReceived += OnSyncDataReceived;
            Sync.OnConnected += OnPeerConnected;
            dotNetRef = DotNetObjectReference.Create(this);
        }

        protected override async Task OnAfterRenderAsync(bool firstRender)
        {
            if (firstRender)
            {
                if (IsHost)
                {
                    // Host Mode: Load job and start listening
                    var job = await Storage.GetJobAsync(JobCode);
                    if (job != null)
                    {
                        currentJob = job;
                    }
                    
                    // Do not initialize Sync until host explicitly opens the lobby
                    hasReceivedInitialData = true;
                    StateHasChanged();
                }
                else
                {
                    // Guest Mode: Initialize PeerJS with random ID, then connect to Host's JobCode
                    await Sync.InitializeAsync();
                    await Sync.ConnectToPeerAsync(JobCode);
                }
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
        }

        private async Task ToggleLobby()
        {
            if (!IsHost) return;

            lobbyIsOpen = !lobbyIsOpen;
            if (lobbyIsOpen)
            {
                await Sync.InitializeAsync(JobCode);
            }
            else
            {
                await Sync.DisconnectAsync();
                isSyncing = false;
            }
            StateHasChanged();
        }

        private async Task AddNewEntry()
        {
            if (!IsHost) return;

            var entry = new TimelineEntry();
            currentJob.Entries.Add(entry);
            currentJob.LastModified = DateTime.UtcNow;

            await Storage.SaveJobAsync(currentJob);
            StateHasChanged(); // This triggers re-render, adding the new card

            if (lobbyIsOpen)
            {
                // Broadcast the full updated job state
                var payload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
            }
        }

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

                if (lobbyIsOpen)
                {
                    // Broadcast to all connected guests
                    var payload = new { type = "timeline_update", entries = currentJob.Entries };
                    await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));
                }

                await Task.Delay(500);
                isSyncing = false;
                StateHasChanged();
            }
        }

        private async void HandleBlur(string entryId)
        {
            // Just an event hook, the real save happens in JS debounce
            await Task.CompletedTask;
        }

        private async void OnPeerConnected(string peerId)
        {
            if (IsHost)
            {
                // Push current state to the newly connected guest
                var payload = new { type = "timeline_update", entries = currentJob.Entries };
                await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(payload));
            }
            else
            {
                StateHasChanged();
            }
        }

        private async void OnSyncDataReceived(string peerId, string dataStr)
        {
            if (IsHost) return; // Host only sends for now

            try
            {
                var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                var document = JsonDocument.Parse(dataStr);
                var type = document.RootElement.GetProperty("type").GetString();

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

                        // Give UI a moment to create any new divs
                        StateHasChanged();
                        await Task.Delay(50);

                        // Update DOM directly to prevent cursor jumping issues on active typing
                        foreach (var entry in currentJob.Entries)
                        {
                            await JSRuntime.InvokeVoidAsync("timelineEditor.setContent", $"zla-editor-{entry.Id}", entry.ContentHtml);
                        }
                    }

                    await Task.Delay(300);
                    isSyncing = false;
                    StateHasChanged();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error parsing sync data: " + ex.Message);
            }
        }

        private void GoHome()
        {
            Navigation.NavigateTo("/");
        }

        private async Task ExportPdf()
        {
            string filename = $"TimelineZLA_{JobCode}_{DateTime.Now:yyyyMMdd}.pdf";
            await JSRuntime.InvokeVoidAsync("pdfExport.exportElement", "timeline-export-root", filename);
        }

        private async Task ShareJobCode()
        {
            await JSRuntime.InvokeVoidAsync("zlaInterop.shareJobCode", JobCode);
        }

        public void Dispose()
        {
            Sync.OnDataReceived -= OnSyncDataReceived;
            Sync.OnConnected -= OnPeerConnected;
            dotNetRef?.Dispose();
        }
    }
}
