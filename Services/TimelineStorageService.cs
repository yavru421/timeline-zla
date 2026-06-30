using Microsoft.JSInterop;
using System.Text.Json;
using System.Threading.Tasks;

namespace PourAndMeasure.Services
{
    public class TimelineStorageService
    {
        private readonly IJSRuntime _jsRuntime;

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
    }
}
