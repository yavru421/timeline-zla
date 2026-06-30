window.imageCompressor = {
    compressImage: function(base64Str, maxWidth = 1200, quality = 0.7) {
        return new Promise((resolve, reject) => {
            if (!base64Str) {
                resolve(base64Str);
                return;
            }
            
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;

                if (width > maxWidth) {
                    height = Math.round((height * maxWidth) / width);
                    width = maxWidth;
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                // Compress and resolve as JPEG
                const compressedDataUrl = canvas.toDataURL('image/jpeg', quality);
                resolve(compressedDataUrl);
            };
            img.onerror = (err) => {
                console.error("Error loading image for compression", err);
                resolve(base64Str); // Fallback to original on error
            };
            img.src = base64Str;
        });
    }
};
