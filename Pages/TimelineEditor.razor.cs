using System;
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
        private Job currentJob = new();
        private DotNetObjectReference<TimelineEditor>? dotNetRef;

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
                        await JSRuntime.InvokeVoidAsync("timelineEditor.setContent", "zla-editor", currentJob.ContentHtml);
                    }
                    
                    await JSRuntime.InvokeVoidAsync("timelineEditor.init", "zla-editor", dotNetRef);
                    await Sync.InitializeAsync(JobCode); // Listen on specific 6-digit code
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
        }

        [JSInvokable]
        public async Task UpdateContent(string html)
        {
            if (!IsHost) return;

            isSyncing = true;
            StateHasChanged();

            currentJob.ContentHtml = html;
            currentJob.LastModified = DateTime.UtcNow;
            
            // Auto-save locally
            await Storage.SaveJobAsync(currentJob);

            // Broadcast to all connected guests
            var payload = new { type = "timeline_update", html = html };
            await Sync.BroadcastDataAsync(JsonSerializer.Serialize(payload));

            // small delay just for UI feedback
            await Task.Delay(500);
            isSyncing = false;
            StateHasChanged();
        }

        private async void OnPeerConnected(string peerId)
        {
            if (IsHost)
            {
                // When a guest connects, immediately push current state
                var payload = new { type = "timeline_update", html = currentJob.ContentHtml };
                await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(payload));
            }
            else
            {
                // We connected to host
                StateHasChanged();
            }
        }

        private async void OnSyncDataReceived(string peerId, string dataStr)
        {
            if (IsHost) return; // Host only sends, doesn't receive for now

            try
            {
                using var doc = JsonDocument.Parse(dataStr);
                var type = doc.RootElement.GetProperty("type").GetString();

                if (type == "timeline_update")
                {
                    var html = doc.RootElement.GetProperty("html").GetString() ?? "";
                    
                    isSyncing = true;
                    hasReceivedInitialData = true;
                    StateHasChanged();

                    // Update DOM directly to prevent re-rendering issues
                    await JSRuntime.InvokeVoidAsync("timelineEditor.setContent", "zla-editor", html);
                    
                    // Also save a local backup for the guest
                    currentJob.JobId = JobCode;
                    currentJob.ContentHtml = html;
                    currentJob.LastModified = DateTime.UtcNow;
                    await Storage.SaveJobAsync(currentJob);

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

        public void Dispose()
        {
            Sync.OnDataReceived -= OnSyncDataReceived;
            Sync.OnConnected -= OnPeerConnected;
            dotNetRef?.Dispose();
        }
    }
}
