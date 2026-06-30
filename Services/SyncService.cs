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
        public event Action<string>? OnConnected;
        public event Action<string>? OnDisconnected;
        public event Action<string, string>? OnDataReceived;
        public event Action<string>? OnError;

        public SyncService(IJSRuntime jsRuntime)
        {
            _jsRuntime = jsRuntime;
        }

        public async Task InitializeAsync(string? customId = null)
        {
            _dotNetRef = DotNetObjectReference.Create(this);
            await _jsRuntime.InvokeVoidAsync("webrtcSync.initialize", _dotNetRef, customId);
        }

        public async Task DisconnectAsync()
        {
            await _jsRuntime.InvokeVoidAsync("webrtcSync.disconnect");
        }

        public async Task<bool> ConnectToPeerAsync(string targetId)
        {
            return await _jsRuntime.InvokeAsync<bool>("webrtcSync.connectToPeer", targetId);
        }

        public async Task<bool> SendDataAsync(string targetId, string data)
        {
            return await _jsRuntime.InvokeAsync<bool>("webrtcSync.sendData", targetId, data);
        }
        
        public async Task<bool> BroadcastDataAsync(string data)
        {
            return await _jsRuntime.InvokeAsync<bool>("webrtcSync.broadcastData", data);
        }

        [JSInvokable("OnPeerIdGenerated")]
        public void OnPeerIdGeneratedCallback(string id)
        {
            OnPeerIdGenerated?.Invoke(id);
        }

        [JSInvokable("OnConnected")]
        public void OnConnectedCallback(string peerId)
        {
            OnConnected?.Invoke(peerId);
        }
        
        [JSInvokable("OnDisconnected")]
        public void OnDisconnectedCallback(string peerId)
        {
            OnDisconnected?.Invoke(peerId);
        }

        [JSInvokable("OnDataReceived")]
        public void OnDataReceivedCallback(string peerId, string data)
        {
            OnDataReceived?.Invoke(peerId, data);
        }
        
        [JSInvokable("OnError")]
        public void OnErrorCallback(string errorMessage)
        {
            OnError?.Invoke(errorMessage);
        }

        public void Dispose()
        {
            _dotNetRef?.Dispose();
        }
    }
}
