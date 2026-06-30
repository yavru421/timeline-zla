using Microsoft.JSInterop;
using System;
using System.Threading.Tasks;

namespace TimelineZLA.Services
{
    public class SyncService : IDisposable
    {
        private readonly IJSRuntime _jsRuntime;
        private DotNetObjectReference<SyncService>? _dotNetRef;
        
        public event Action<string>? OnPeerIdGenerated;
        public event Action? OnConnected;
        public event Action<string>? OnDataReceived;

        public SyncService(IJSRuntime jsRuntime)
        {
            _jsRuntime = jsRuntime;
        }

        public async Task InitializeAsync()
        {
            _dotNetRef = DotNetObjectReference.Create(this);
            await _jsRuntime.InvokeVoidAsync("webrtcSync.initialize", _dotNetRef);
        }

        public async Task<bool> ConnectToPeerAsync(string targetId)
        {
            return await _jsRuntime.InvokeAsync<bool>("webrtcSync.connectToPeer", targetId);
        }

        public async Task<bool> SendDataAsync(string data)
        {
            return await _jsRuntime.InvokeAsync<bool>("webrtcSync.sendData", data);
        }

        [JSInvokable("OnPeerIdGenerated")]
        public void OnPeerIdGeneratedCallback(string id)
        {
            OnPeerIdGenerated?.Invoke(id);
        }

        [JSInvokable("OnConnected")]
        public void OnConnectedCallback()
        {
            OnConnected?.Invoke();
        }

        [JSInvokable("OnDataReceived")]
        public void OnDataReceivedCallback(string data)
        {
            OnDataReceived?.Invoke(data);
        }

        public void Dispose()
        {
            _dotNetRef?.Dispose();
        }
    }
}

