using System;
using System.Collections.Generic;

namespace TimelineZLA.Models
{
    public class TimelineEntry
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public string ContentHtml { get; set; } = string.Empty;

        // Feature #3: Pin/Star
        public bool IsPinned { get; set; } = false;

        // Feature #4: Entry type (note | photo | alert | milestone | check)
        public string EntryType { get; set; } = "note";

        // Feature #1: Tags
        public List<string> Tags { get; set; } = new();
    }
}
