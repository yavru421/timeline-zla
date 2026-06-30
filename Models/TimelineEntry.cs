using System;

namespace TimelineZLA.Models
{
    public enum EntryType
    {
        Note,
        Photo,
        Milestone
    }

    public class TimelineEntry
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string JobId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Notes { get; set; } = string.Empty;
        public string? ImageUrl { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public EntryType Type { get; set; } = EntryType.Note;
    }
}
