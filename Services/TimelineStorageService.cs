using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.JSInterop;
using TimelineZLA.Models;

namespace TimelineZLA.Services
{
    public class TimelineStorageService
    {
        private readonly IJSRuntime _jsRuntime;

        public TimelineStorageService(IJSRuntime jsRuntime)
        {
            _jsRuntime = jsRuntime;
        }

        public async Task SaveJobAsync(Job job)
        {
            await _jsRuntime.InvokeVoidAsync("storage.setItem", $"job_{job.JobId}", job);
        }

        public async Task<Job?> GetJobAsync(string jobId)
        {
            return await _jsRuntime.InvokeAsync<Job?>("storage.getItem", $"job_{jobId}");
        }

        public async Task<List<Job>> GetAllJobsAsync()
        {
            var jobs = new List<Job>();
            var keys = await _jsRuntime.InvokeAsync<List<string>>("storage.getKeysWithPrefix", "job_");
            
            foreach (var key in keys)
            {
                var job = await _jsRuntime.InvokeAsync<Job?>("storage.getItem", key);
                if (job != null)
                {
                    jobs.Add(job);
                }
            }
            return jobs;
        }

        public async Task DeleteJobAsync(string jobId)
        {
            await _jsRuntime.InvokeVoidAsync("storage.removeItem", $"job_{jobId}");
        }
    }
}
