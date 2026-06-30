using System;

namespace TimelineZLA.Models
{
    public class TimelineEntry
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public string ContentHtml { get; set; } = string.Empty;
    }
}
