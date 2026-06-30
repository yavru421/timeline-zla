window.timelineEditor = {
    init: function (elementId, dotNetRef) {
        const editor = document.getElementById(elementId);
        if (!editor) return;

        // Prevent attaching multiple listeners if re-initialized
        if (editor.dataset.initialized) return;
        editor.dataset.initialized = "true";

        let debounceTimer;
        const entryId = elementId.replace('zla-editor-', '');

        // Listen for typing
        editor.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                dotNetRef.invokeMethodAsync('UpdateContent', entryId, editor.innerHTML);
            }, 500);
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
                    
                    // Convert blob to Data URL
                    const reader = new FileReader();
                    reader.onload = async function (event) {
                        const originalDataUrl = event.target.result;
                        
                        try {
                            // Compress image (max width 1200, quality 0.7)
                            const compressedDataUrl = await window.imageCompressor.compressImage(originalDataUrl, 1200, 0.7);
                            
                            // Insert into editor at cursor
                            document.execCommand('insertImage', false, compressedDataUrl);
                            
                            // Trigger input event to save
                            editor.dispatchEvent(new Event('input'));
                        } catch (err) {
                            console.error("Failed to compress pasted image", err);
                        }
                    };
                    reader.readAsDataURL(blob);
                }
            }

            // If we handled an image, prevent default pasting
            if (hasImage) {
                e.preventDefault();
            }
        });
    },
    
    setContent: function (elementId, html) {
        const editor = document.getElementById(elementId);
        if (editor && editor.innerHTML !== html) {
            editor.innerHTML = html;
        }
    }
};
