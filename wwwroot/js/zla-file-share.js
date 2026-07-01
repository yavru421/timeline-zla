window.zlaFileShare = {

    // ─── Host: open a file or folder picker ─────────────────────────────────────
    openPicker: function (dotNetRef, mode) {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.style.display = 'none';

        if (mode === 'folder') {
            input.webkitdirectory = true;
            input.directory = true;
        } else {
            // Support images, PDFs, audio, video, docs, text
            input.accept = [
                'image/*',
                'application/pdf',
                'audio/*',
                'video/mp4',
                'video/quicktime',
                'video/x-matroska',
                '.txt', '.csv', '.docx', '.xlsx', '.doc', '.xls', '.zip'
            ].join(',');
        }

        document.body.appendChild(input);
        input.onchange = async (e) => {
            document.body.removeChild(input);
            const files = Array.from(e.target.files);
            if (files.length === 0) return;
            await window.zlaFileShare.processFiles(files, dotNetRef);
        };
        input.click();
    },

    // ─── Process selected files and send each one to Blazor ─────────────────────
    processFiles: async function (files, dotNetRef) {
        const MAX_PER_FILE = 25 * 1024 * 1024; // 25MB hard limit per file
        const WARN_TOTAL   = 50 * 1024 * 1024; // 50MB soft warning

        // Warn if total is large (before compression)
        const rawTotal = files.reduce((s, f) => s + f.size, 0);
        if (rawTotal > WARN_TOTAL) {
            const mb = (rawTotal / 1024 / 1024).toFixed(0);
            const go = confirm(
                `⚠️ ${files.length} files selected (${mb}MB raw).\n\n` +
                `Images will be compressed automatically. Large non-image files ` +
                `(videos, ZIPs) are sent as-is and may be slow.\n\nContinue?`
            );
            if (!go) return;
        }

        await dotNetRef.invokeMethodAsync('OnFileShareStart', files.length);

        let processed = 0;
        for (const file of files) {
            try {
                let base64Data;
                let finalSize;

                if (file.size > MAX_PER_FILE) {
                    // Too large — notify and skip
                    await dotNetRef.invokeMethodAsync(
                        'OnFileShareSkipped',
                        file.name,
                        `File too large (${(file.size / 1024 / 1024).toFixed(0)}MB). Max is 25MB.`
                    );
                    processed++;
                    await dotNetRef.invokeMethodAsync('OnFileShareProgress', processed, files.length, file.name);
                    continue;
                }

                if (file.type.startsWith('image/')) {
                    // Compress images before sharing
                    const raw = await window.zlaFileShare._readAsDataUrl(file);
                    const compressed = await window.imageCompressor.compressImage(raw, 1600, 0.82);
                    // Strip the data URL prefix to get pure base64
                    base64Data = compressed.split(',')[1];
                    finalSize = Math.round(base64Data.length * 0.75); // approx decoded bytes
                } else {
                    const raw = await window.zlaFileShare._readAsDataUrl(file);
                    base64Data = raw.split(',')[1];
                    finalSize = file.size;
                }

                await dotNetRef.invokeMethodAsync(
                    'OnFileShareReceived',
                    file.name,
                    file.type || 'application/octet-stream',
                    base64Data,
                    finalSize
                );

                processed++;
                await dotNetRef.invokeMethodAsync('OnFileShareProgress', processed, files.length, file.name);

            } catch (err) {
                console.error('Failed to process file:', file.name, err);
                processed++;
            }
        }

        await dotNetRef.invokeMethodAsync('OnFileShareDone');
    },

    // ─── Guest/Host: download a shared file ────────────────────────────────────
    downloadFile: function (filename, mimeType, base64Data) {
        try {
            const byteChars = atob(base64Data);
            const byteNums = new Array(byteChars.length);
            for (let i = 0; i < byteChars.length; i++) {
                byteNums[i] = byteChars.charCodeAt(i);
            }
            const blob = new Blob([new Uint8Array(byteNums)], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 3000);
        } catch (err) {
            console.error('Download failed:', err);
        }
    },

    // ─── Setup drag-and-drop on a panel element ─────────────────────────────────
    initDropZone: function (elementId, dotNetRef) {
        const el = document.getElementById(elementId);
        if (!el || el.dataset.dropInit) return;
        el.dataset.dropInit = 'true';

        el.addEventListener('dragover', (e) => {
            e.preventDefault();
            el.classList.add('drag-over');
        });
        el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
        el.addEventListener('drop', async (e) => {
            e.preventDefault();
            el.classList.remove('drag-over');
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                await window.zlaFileShare.processFiles(files, dotNetRef);
            }
        });
    },

    _readAsDataUrl: function (file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
};
