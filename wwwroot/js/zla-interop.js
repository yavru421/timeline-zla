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
    },

    // Feature #7: Pleasant 2-tone chime when a guest connects
    playConnectSound: function () {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const playTone = (freq, startTime, duration, volume = 0.25) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'sine';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(volume, startTime);
                gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
                osc.start(startTime);
                osc.stop(startTime + duration);
            };
            const t = ctx.currentTime;
            playTone(880, t, 0.18);
            playTone(1100, t + 0.18, 0.25);
        } catch (e) {
            // Audio not available — silent fail
        }
    }
};
