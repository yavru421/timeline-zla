window.webrtcSync = {
    peer: null,
    connections: {},
    dotNetRef: null,

    initialize: function(dotNetReference, customId) {
        this.dotNetRef = dotNetReference;
        
        // Use deterministic session code if provided
        const config = { debug: 3 };
        if (customId) {
            this.peer = new Peer(customId, config);
        } else {
            this.peer = new Peer(config);
        }
        
        this.peer.on('open', (id) => {
            console.log('My peer ID is: ' + id);
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnPeerIdGenerated', id);
            }
        });

        this.peer.on('connection', (connection) => {
            this.connections[connection.peer] = connection;
            this.setupConnection(connection);
        });

        this.peer.on('error', (err) => {
            console.error('PeerJS error:', err);
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnError', err.message);
            }
        });
    },

    connectToPeer: function(targetId) {
        if (!this.peer) return false;
        
        if (this.connections[targetId] && this.connections[targetId].open) {
            return true;
        }

        const conn = this.peer.connect(targetId);
        this.connections[targetId] = conn;
        this.setupConnection(conn);
        return true;
    },

    setupConnection: function(conn) {
        conn.on('open', () => {
            console.log('Connected to peer: ' + conn.peer);
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnConnected', conn.peer);
            }
        });

        conn.on('data', (data) => {
            if (this.dotNetRef) {
                // Ensure data is stringified JSON before passing to interop if it's an object,
                // but usually we send strings
                const dataStr = typeof data === 'string' ? data : JSON.stringify(data);
                this.dotNetRef.invokeMethodAsync('OnDataReceived', conn.peer, dataStr);
            }
        });
        
        conn.on('close', () => {
            console.log('Connection closed: ' + conn.peer);
            delete this.connections[conn.peer];
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnDisconnected', conn.peer);
            }
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
        if (this.peer) {
            this.peer.destroy();
            this.peer = null;
        }
        this.connections = {};
    }
};
