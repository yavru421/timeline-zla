window.pdfExport = {
    exportElement: function (elementId, filename) {
        var element = document.getElementById(elementId);
        if (!element) {
            console.error('Element not found: ' + elementId);
            return;
        }
        var opt = {
            margin:       1,
            filename:     filename,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };
        html2pdf().set(opt).from(element).save();
    }
};
