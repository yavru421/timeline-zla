window.zlaInterop = {
    shareJobCode: async function (jobCode) {
        const guestUrl = `${window.location.origin}/job/${jobCode}?role=guest`;
        const shareData = {
            title: 'Join my TimelineZLA',
            text: `Join my live job timeline (code: ${jobCode})`,
            url: guestUrl
        };
        if (navigator.share) {
            try { await navigator.share(shareData); return true; } catch (err) { }
        }
        try {
            await navigator.clipboard.writeText(guestUrl);
            alert(`Guest link copied!\n\n${guestUrl}`);
            return true;
        } catch (err) { return false; }
    },

    // Feature #7: Theme management
    getTheme: function () {
        return localStorage.getItem('zla-theme') || 'dark';
    },

    setTheme: function (theme) {
        localStorage.setItem('zla-theme', theme);
        if (theme === 'dark') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    },

    // Feature #6: PWA install prompt
    registerPwaCallback: function (dotNetRef) {
        window.dotNetPwaRef = dotNetRef;
        // If prompt was already captured before Blazor loaded, notify immediately
        if (window._pwaPrompt) {
            dotNetRef.invokeMethodAsync('OnInstallAvailable');
        }
    },

    canInstallPwa: function () {
        return !!window._pwaPrompt;
    },

    triggerInstallPrompt: async function () {
        if (!window._pwaPrompt) return false;
        window._pwaPrompt.prompt();
        const { outcome } = await window._pwaPrompt.userChoice;
        window._pwaPrompt = null;
        return outcome === 'accepted';
    },

    showIosInstallGuide: function () {
        // Returns true if this is iOS Safari (needs manual Add to Home Screen)
        const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
        const isStandalone = window.navigator.standalone === true;
        return isIos && !isStandalone;
    },

    // Feature #7: Guest connect chime
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
        } catch (e) { }
    }
};
