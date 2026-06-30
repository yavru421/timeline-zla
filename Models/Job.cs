using System;

namespace TimelineZLA.Models
{
    public class Job
    {
        public string JobId { get; set; } = string.Empty; // 6-digit code
        public string JobName { get; set; } = string.Empty;
        public string ContentHtml { get; set; } = string.Empty; // Rich text blob
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime LastModified { get; set; } = DateTime.UtcNow;
    }
}
