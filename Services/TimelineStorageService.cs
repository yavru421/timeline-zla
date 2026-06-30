using Microsoft.JSInterop;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using TimelineZLA.Models;

namespace TimelineZLA.Services
{
    public class TimelineStorageService
    {
        private readonly IJSRuntime _jsRuntime;
        private const string JOBS_INDEX_KEY = "jobs_index";

        public TimelineStorageService(IJSRuntime jsRuntime)
        {
            _jsRuntime = jsRuntime;
        }

        public async Task<bool> SaveDataAsync<T>(string key, T data)
        {
            var json = JsonSerializer.Serialize(data);
            return await _jsRuntime.InvokeAsync<bool>("timelineStorage.saveData", key, json);
        }

        public async Task<T?> LoadDataAsync<T>(string key)
        {
            var json = await _jsRuntime.InvokeAsync<string>("timelineStorage.loadData", key);
            if (string.IsNullOrEmpty(json)) return default;
            return JsonSerializer.Deserialize<T>(json);
        }

        public async Task<bool> RemoveDataAsync(string key)
        {
            return await _jsRuntime.InvokeAsync<bool>("timelineStorage.removeData", key);
        }

        // --- Job CRUD ---
        
        public async Task<List<Job>> GetAllJobsAsync()
        {
            var jobs = await LoadDataAsync<List<Job>>(JOBS_INDEX_KEY);
            return jobs ?? new List<Job>();
        }

        public async Task<Job?> GetJobAsync(string jobId)
        {
            var jobs = await GetAllJobsAsync();
            return jobs.FirstOrDefault(j => j.JobId == jobId);
        }

        public async Task<bool> SaveJobAsync(Job job)
        {
            var jobs = await GetAllJobsAsync();
            var existing = jobs.FirstOrDefault(j => j.JobId == job.JobId);
            if (existing != null)
            {
                jobs.Remove(existing);
            }
            job.LastModified = System.DateTime.UtcNow;
            jobs.Add(job);
            return await SaveDataAsync(JOBS_INDEX_KEY, jobs);
        }

        public async Task<bool> DeleteJobAsync(string jobId)
        {
            var jobs = await GetAllJobsAsync();
            var job = jobs.FirstOrDefault(j => j.JobId == jobId);
            if (job != null)
            {
                jobs.Remove(job);
                await SaveDataAsync(JOBS_INDEX_KEY, jobs);
                // Also clean up entries
                await RemoveDataAsync($"job_{jobId}_entries");
                return true;
            }
            return false;
        }

        // --- Entry CRUD ---

        public async Task<List<TimelineEntry>> GetEntriesForJobAsync(string jobId)
        {
            var key = $"job_{jobId}_entries";
            var entries = await LoadDataAsync<List<TimelineEntry>>(key);
            return entries ?? new List<TimelineEntry>();
        }

        public async Task<bool> SaveEntryAsync(TimelineEntry entry)
        {
            var entries = await GetEntriesForJobAsync(entry.JobId);
            
            // Last-write-wins dedup based on Timestamp (assuming UTC is used consistently)
            var existing = entries.FirstOrDefault(e => e.Id == entry.Id);
            if (existing != null)
            {
                if (entry.Timestamp > existing.Timestamp)
                {
                    entries.Remove(existing);
                    entries.Add(entry);
                }
            }
            else
            {
                entries.Add(entry);
            }
            
            // Sort by Timestamp descending for the timeline view
            entries = entries.OrderByDescending(e => e.Timestamp).ToList();
            
            // Update job's last modified
            var job = await GetJobAsync(entry.JobId);
            if (job != null)
            {
                job.LastModified = System.DateTime.UtcNow;
                await SaveJobAsync(job);
            }

            return await SaveDataAsync($"job_{entry.JobId}_entries", entries);
        }

        public async Task<bool> SaveEntriesBatchAsync(string jobId, List<TimelineEntry> newEntries)
        {
            var entries = await GetEntriesForJobAsync(jobId);
            
            foreach (var entry in newEntries)
            {
                var existing = entries.FirstOrDefault(e => e.Id == entry.Id);
                if (existing != null)
                {
                    if (entry.Timestamp > existing.Timestamp)
                    {
                        entries.Remove(existing);
                        entries.Add(entry);
                    }
                }
                else
                {
                    entries.Add(entry);
                }
            }
            
            entries = entries.OrderByDescending(e => e.Timestamp).ToList();
            return await SaveDataAsync($"job_{jobId}_entries", entries);
        }

        public async Task<bool> DeleteEntryAsync(string jobId, string entryId)
        {
            var entries = await GetEntriesForJobAsync(jobId);
            var entry = entries.FirstOrDefault(e => e.Id == entryId);
            if (entry != null)
            {
                entries.Remove(entry);
                return await SaveDataAsync($"job_{jobId}_entries", entries);
            }
            return false;
        }
    }
}
