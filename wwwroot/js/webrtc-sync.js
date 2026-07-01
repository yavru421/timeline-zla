window.webrtcSync = {
    peer: null,
    connections: {},
    dotNetRef: null,
    _retryTimer: null,
    _retryCount: 0,
    _maxRetries: 8,

    initialize: function(dotNetReference, customId) {
        this.dotNetRef = dotNetReference;
        this._retryCount = 0;
        this._createPeer(customId);
    },

    _createPeer: function(customId) {
        const self = this;

        // Clean up any existing peer before creating a new one
        if (this.peer && !this.peer.destroyed) {
            this.peer.destroy();
        }

        const config = { debug: 1 };
        this.peer = customId ? new Peer(customId, config) : new Peer(config);

        this.peer.on('open', (id) => {
            console.log('[PeerJS] Open with ID:', id);
            self._retryCount = 0;
            if (self.dotNetRef) {
                self.dotNetRef.invokeMethodAsync('OnPeerIdGenerated', id);
            }
        });

        this.peer.on('connection', (connection) => {
            self.connections[connection.peer] = connection;
            self.setupConnection(connection);
        });

        this.peer.on('error', (err) => {
            console.error('[PeerJS] Error:', err.type, err.message);

            if (err.type === 'unavailable-id') {
                // Host: the 6-digit ID is already registered from a previous session.
                // Wait a moment and try again — PeerJS server should release it within ~30s.
                console.warn('[PeerJS] ID unavailable, retrying in 3s...');
                if (self._retryCount < self._maxRetries) {
                    self._retryCount++;
                    setTimeout(() => self._createPeer(customId), 3000);
                } else {
                    if (self.dotNetRef) {
                        self.dotNetRef.invokeMethodAsync('OnError', 'Host ID unavailable after retries. Please refresh.');
                    }
                }
                return;
            }

            if (err.type === 'peer-unavailable') {
                // Guest: the host peer ID was not found (host not online yet, or connection dropped)
                if (self._retryCount < self._maxRetries) {
                    self._retryCount++;
                    const wait = Math.min(2000 * self._retryCount, 10000);
                    console.warn(`[PeerJS] Host not found. Retry ${self._retryCount}/${self._maxRetries} in ${wait}ms`);
                    if (self.dotNetRef) {
                        self.dotNetRef.invokeMethodAsync('OnRetrying', self._retryCount, self._maxRetries);
                    }
                    // The retry is driven from C# via OnGuestPeerReady -> ConnectToPeer,
                    // but peer-unavailable means peer exists but host is gone. Retry connect.
                    setTimeout(() => {
                        if (self._lastTargetId) self.connectToPeer(self._lastTargetId);
                    }, wait);
                } else {
                    if (self.dotNetRef) {
                        self.dotNetRef.invokeMethodAsync('OnError', 'Could not reach host. Make sure the host has the job open.');
                    }
                }
                return;
            }

            // All other errors — surface to UI
            if (self.dotNetRef) {
                self.dotNetRef.invokeMethodAsync('OnError', err.message || err.type);
            }
        });

        this.peer.on('disconnected', () => {
            console.warn('[PeerJS] Disconnected from signaling server. Reconnecting...');
            if (!self.peer.destroyed) {
                self.peer.reconnect();
            }
        });
    },

    connectToPeer: function(targetId) {
        if (!this.peer || this.peer.destroyed) return false;
        this._lastTargetId = targetId;

        if (this.connections[targetId] && this.connections[targetId].open) {
            return true;
        }

        const conn = this.peer.connect(targetId, { reliable: true });
        this.connections[targetId] = conn;
        this.setupConnection(conn);
        return true;
    },

    setupConnection: function(conn) {
        const self = this;

        conn.on('open', () => {
            console.log('[PeerJS] Data channel open with:', conn.peer);
            self._retryCount = 0;
            if (self.dotNetRef) {
                self.dotNetRef.invokeMethodAsync('OnConnected', conn.peer);
            }
        });

        conn.on('data', (data) => {
            if (self.dotNetRef) {
                const dataStr = typeof data === 'string' ? data : JSON.stringify(data);
                self.dotNetRef.invokeMethodAsync('OnDataReceived', conn.peer, dataStr);
            }
        });

        conn.on('close', () => {
            console.log('[PeerJS] Connection closed:', conn.peer);
            delete self.connections[conn.peer];
            if (self.dotNetRef) {
                self.dotNetRef.invokeMethodAsync('OnDisconnected', conn.peer);
            }
        });

        conn.on('error', (err) => {
            console.error('[PeerJS] Connection error:', err);
        });
    },

    sendData: function(targetId, data) {
        const conn = this.connections[targetId];
        if (conn && conn.open) {
            conn.send(data);
            return true;
        }
        return false;
    },

    broadcastData: function(data) {
        let sent = false;
        for (const id in this.connections) {
            const conn = this.connections[id];
            if (conn && conn.open) {
                conn.send(data);
                sent = true;
            }
        }
        return sent;
    },

    disconnect: function() {
        clearTimeout(this._retryTimer);
        if (this.peer) {
            this.peer.destroy();
            this.peer = null;
        }
        this.connections = {};
        this._lastTargetId = null;
        this._retryCount = 0;
    }
};
