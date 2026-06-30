using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Forms;
using Microsoft.JSInterop;
using TimelineZLA.Models;
using System.Text.Json;

namespace TimelineZLA.Pages
{
    public partial class Timeline : IDisposable
    {
        [Parameter]
        public string JobId { get; set; } = string.Empty;

        private Job? job;
        private List<TimelineEntry> entries = new();
        private TimelineEntry newEntry = new();
        
        private string? myPeerId;
        private bool isCompressing = false;
        private bool hasImage = false;
        
        protected override async Task OnInitializedAsync()
        {
            job = await Storage.GetJobAsync(JobId);
            if (job != null)
            {
                newEntry.JobId = job.JobId;
                await LoadEntries();
            }

            // Setup Sync Service for this worker (generates session code)
            Sync.OnPeerIdGenerated += OnPeerIdGenerated;
            Sync.OnDataReceived += OnSyncRequestReceived;
            
            // Generate a 6-digit session code deterministically or randomly for this session
            var randomSessionCode = new Random().Next(100000, 999999).ToString();
            await Sync.InitializeAsync(randomSessionCode);
        }

        private async Task LoadEntries()
        {
            entries = await Storage.GetEntriesForJobAsync(JobId);
            StateHasChanged();
        }

        private void OnPeerIdGenerated(string peerId)
        {
            myPeerId = peerId;
            StateHasChanged();
        }

        private async void OnSyncRequestReceived(string peerId, string dataStr)
        {
            try
            {
                using var doc = JsonDocument.Parse(dataStr);
                var type = doc.RootElement.GetProperty("type").GetString();
                
                if (type == "sync_request")
                {
                    // Admin is requesting data
                    var reqJobId = doc.RootElement.GetProperty("jobId").GetString();
                    
                    if (reqJobId == "all" || reqJobId == JobId)
                    {
                        // Send current job and all its entries
                        var currentJob = await Storage.GetJobAsync(JobId);
                        var currentEntries = await Storage.GetEntriesForJobAsync(JobId);
                        
                        var responseObj = new
                        {
                            type = "sync_response",
                            jobId = JobId,
                            job = currentJob,
                            entries = currentEntries
                        };
                        
                        await Sync.SendDataAsync(peerId, JsonSerializer.Serialize(responseObj));
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing sync request: {ex.Message}");
            }
        }

        private async Task HandleFileSelected(InputFileChangeEventArgs e)
        {
            isCompressing = true;
            hasImage = false;
            StateHasChanged();

            try
            {
                var file = e.File;
                // Max 10MB to read into memory before compression
                var maxAllowedSize = 10 * 1024 * 1024;
                using var stream = file.OpenReadStream(maxAllowedSize);
                
                using var memoryStream = new System.IO.MemoryStream();
                await stream.CopyToAsync(memoryStream);
                var base64 = Convert.ToBase64String(memoryStream.ToArray());
                var dataUrl = $"data:{file.ContentType};base64,{base64}";

                // Call JS interop to compress
                var compressedDataUrl = await JSRuntime.InvokeAsync<string>("imageCompressor.compressImage", dataUrl, 1200, 0.7);
                
                newEntry.ImageUrl = compressedDataUrl;
                hasImage = true;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error compressing image: {ex.Message}");
            }
            finally
            {
                isCompressing = false;
                StateHasChanged();
            }
        }

        private async Task AddEntry()
        {
            if (isCompressing) return;

            newEntry.Id = Guid.NewGuid().ToString();
            newEntry.Timestamp = DateTime.UtcNow; // UTC for deduplication
            
            await Storage.SaveEntryAsync(newEntry);
            await LoadEntries();

            // Broadcast new entry to any connected Admins
            var responseObj = new
            {
                type = "sync_response",
                jobId = JobId,
                job = job,
                entries = entries // Send the full updated list for simplicity, or just the diff
            };
            await Sync.BroadcastDataAsync(JsonSerializer.Serialize(responseObj));

            // Reset form
            newEntry = new TimelineEntry { JobId = JobId };
            hasImage = false;
        }

        private async Task ExportTimeline()
        {
            await PdfExport.ExportToPdfAsync("timeline-export-area", $"Timeline_Export_{DateTime.Now:yyyyMMdd_HHmm}.pdf");
        }

        public void Dispose()
        {
            Sync.OnPeerIdGenerated -= OnPeerIdGenerated;
            Sync.OnDataReceived -= OnSyncRequestReceived;
        }
    }
}
