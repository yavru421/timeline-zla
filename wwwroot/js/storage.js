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
    }
};
