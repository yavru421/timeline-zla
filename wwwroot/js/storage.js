window.timelineStorage = {
    saveData: async function(key, data) {
        try {
            await localforage.setItem(key, data);
            return true;
        } catch (err) {
            console.error('Error saving data to localforage', err);
            return false;
        }
    },
    loadData: async function(key) {
        try {
            return await localforage.getItem(key);
        } catch (err) {
            console.error('Error loading data from localforage', err);
            return null;
        }
    },
    removeData: async function(key) {
        try {
            await localforage.removeItem(key);
            return true;
        } catch (err) {
            console.error('Error removing data from localforage', err);
            return false;
        }
    },
    getAllKeys: async function() {
        try {
            return await localforage.keys();
        } catch (err) {
            console.error('Error getting keys from localforage', err);
            return [];
        }
    },
    getKeysWithPrefix: async function(prefix) {
        try {
            const keys = await localforage.keys();
            return keys.filter(k => k.startsWith(prefix));
        } catch (err) {
            console.error('Error getting keys with prefix', err);
            return [];
        }
    }
};
