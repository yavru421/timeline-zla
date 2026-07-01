window.zlaInterop = {
    shareJobCode: async function (jobCode) {
        // Deep-link directly to the job in guest mode — recipient taps and lands right in
        const guestUrl = `${window.location.origin}/job/${jobCode}?role=guest`;
        const shareData = {
            title: 'Join my TimelineZLA',
            text: `Join my live job timeline (code: ${jobCode})`,
            url: guestUrl
        };
        
        if (navigator.share) {
            try {
                await navigator.share(shareData);
                return true;
            } catch (err) {
                console.log('Share canceled or failed', err);
            }
        }
        
        // Fallback: copy the direct guest link to clipboard
        try {
            await navigator.clipboard.writeText(guestUrl);
            alert(`Guest link copied!\n\n${guestUrl}`);
            return true;
        } catch (err) {
            console.error('Failed to copy', err);
            return false;
        }
    }
};
