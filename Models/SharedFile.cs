using System;

namespace TimelineZLA.Models
{
    public class SharedFile
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string Name { get; set; } = string.Empty;
        public string MimeType { get; set; } = string.Empty;
        public string Base64Data { get; set; } = string.Empty;
        public long SizeBytes { get; set; }

        public string FriendlySize =>
            SizeBytes < 1024 ? $"{SizeBytes}B" :
            SizeBytes < 1024 * 1024 ? $"{SizeBytes / 1024}KB" :
            $"{SizeBytes / 1024 / 1024.0:F1}MB";

        public string Icon =>
            MimeType.StartsWith("image/") ? "image" :
            MimeType == "application/pdf" ? "picture_as_pdf" :
            MimeType.StartsWith("audio/") ? "audio_file" :
            MimeType.StartsWith("video/") ? "videocam" :
            "insert_drive_file";
    }
}
