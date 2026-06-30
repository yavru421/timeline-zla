using System;

namespace TimelineZLA.Models
{
    public class Job
    {
        public string JobId { get; set; } = string.Empty; // 6-digit code
        public string JobName { get; set; } = string.Empty;
        public List<TimelineEntry> Entries { get; set; } = new();
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime LastModified { get; set; } = DateTime.UtcNow;
    }
}
