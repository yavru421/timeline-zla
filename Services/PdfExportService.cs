using Microsoft.JSInterop;

namespace PourAndMeasure.Services
{
    public class PdfExportService
    {
        private readonly IJSRuntime _jsRuntime;

        public PdfExportService(IJSRuntime jsRuntime)
        {
            _jsRuntime = jsRuntime;
        }

        public async Task ExportToPdfAsync(string elementId, string filename)
        {
            await _jsRuntime.InvokeVoidAsync("pdfExport.exportElement", elementId, filename);
        }
    }
}
