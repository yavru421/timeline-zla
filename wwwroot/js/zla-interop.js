window.zlaInterop = {
    shareJobCode: async function (jobCode) {
        const url = window.location.origin;
        const text = `Join my TimelineZLA. Open ${url} and enter my secure 6-digit access code: ${jobCode}`;
        
        if (navigator.share) {
            try {
                await navigator.share({
                    title: 'TimelineZLA Access Code',
                    text: text
                });
                return true;
            } catch (err) {
                console.log('Share canceled or failed', err);
            }
        }
        
        // Fallback to clipboard
        try {
            await navigator.clipboard.writeText(text);
            alert("Access code copied to clipboard!");
            return true;
        } catch (err) {
            console.error('Failed to copy', err);
            return false;
        }
    }
};
