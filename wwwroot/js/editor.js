window.timelineEditor = {
    init: function (elementId, dotNetRef) {
        const editor = document.getElementById(elementId);
        if (!editor) return;
        if (editor.dataset.initialized) return;
        editor.dataset.initialized = 'true';

        let debounceTimer;
        const entryId = elementId.replace('zla-editor-', '');

        editor.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                dotNetRef.invokeMethodAsync('UpdateContent', entryId, editor.innerHTML);
            }, 800);
        });

        // Intercept paste for images
        editor.addEventListener('paste', async function (e) {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            let hasImage = false;
            for (let index in items) {
                const item = items[index];
                if (item.kind === 'file' && item.type.startsWith('image/')) {
                    hasImage = true;
                    const blob = item.getAsFile();
                    const reader = new FileReader();
                    reader.onload = async function (event) {
                        try {
                            const compressed = await window.imageCompressor.compressImage(event.target.result, 1200, 0.7);
                            document.execCommand('insertImage', false, compressed);
                            editor.dispatchEvent(new Event('input'));
                        } catch (err) {
                            console.error('Failed to compress pasted image', err);
                        }
                    };
                    reader.readAsDataURL(blob);
                }
            }
            if (hasImage) e.preventDefault();
        });
    },

    setContent: function (elementId, html) {
        const editor = document.getElementById(elementId);
        if (editor && editor.innerHTML !== html) {
            editor.innerHTML = html;
        }
    },

    // Used by the explicit Save button — reads current content immediately
    getContent: function (elementId) {
        const el = document.getElementById(elementId);
        return el ? el.innerHTML : '';
    }
};
