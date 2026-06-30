window.webrtcSync = {
    peer: null,
    conn: null,
    dotNetRef: null,

    initialize: function(dotNetReference) {
        this.dotNetRef = dotNetReference;
        // Use PeerJS public server
        this.peer = new Peer();
        
        this.peer.on('open', (id) => {
            console.log('My peer ID is: ' + id);
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnPeerIdGenerated', id);
            }
        });

        this.peer.on('connection', (connection) => {
            this.conn = connection;
            this.setupConnection();
        });

        this.peer.on('error', (err) => {
            console.error('PeerJS error:', err);
        });
    },

    connectToPeer: function(targetId) {
        if (!this.peer) return false;
        this.conn = this.peer.connect(targetId);
        this.setupConnection();
        return true;
    },

    setupConnection: function() {
        if (!this.conn) return;
        this.conn.on('open', () => {
            console.log('Connected to peer');
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnConnected');
            }
        });

        this.conn.on('data', (data) => {
            if (this.dotNetRef) {
                this.dotNetRef.invokeMethodAsync('OnDataReceived', data);
            }
        });
    },

    sendData: function(data) {
        if (this.conn && this.conn.open) {
            this.conn.send(data);
            return true;
        }
        return false;
    }
};
