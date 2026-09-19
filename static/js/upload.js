/**
 * Excel upload page logic: drag & drop, progress simulation, result display.
 */
document.addEventListener('DOMContentLoaded', function () {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
    const ALLOWED_EXTENSION = '.xlsx';

    const progressPanel = document.getElementById('progressPanel');
    const progressBar = document.getElementById('progressBar');
    const progressFileName = document.getElementById('progressFileName');
    const resultPanel = document.getElementById('resultPanel');
    const resultAlert = document.getElementById('resultAlert');
    const resultTitle = document.getElementById('resultTitle');
    const resultMessage = document.getElementById('resultMessage');
    const uploadsTable = document.getElementById('uploadsTable');
    const refreshUploads = document.getElementById('refreshUploads');

    // Initialize drop zones
    document.querySelectorAll('.upload-card').forEach(function (card) {
        initializeUploadCard(card);
    });

    loadRecentUploads();

    if (refreshUploads) {
        refreshUploads.addEventListener('click', function () {
            const icon = this.querySelector('i');
            if (icon) icon.classList.add('ti-spin');
            loadRecentUploads().finally(function () {
                if (icon) icon.classList.remove('ti-spin');
            });
        });
    }

    function initializeUploadCard(card) {
        const dropZone = card.querySelector('.drop-zone');
        const fileInput = card.querySelector('.drop-zone-input');
        const uploadButton = card.querySelector('.upload-submit');
        const removeButton = card.querySelector('.remove-file');
        const endpoint = card.getAttribute('data-endpoint');

        if (!dropZone || !fileInput || !uploadButton) return;

        // Click on drop zone triggers file input
        dropZone.addEventListener('click', function (e) {
            if (e.target.closest('.remove-file')) return;
            fileInput.click();
        });

        // File selected via input
        fileInput.addEventListener('change', function () {
            handleFileSelection(card, fileInput.files[0]);
        });

        // Drag events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(function (eventName) {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(function (eventName) {
            dropZone.addEventListener(eventName, function () {
                dropZone.classList.add('drag-over');
            }, false);
        });

        ['dragleave', 'drop'].forEach(function (eventName) {
            dropZone.addEventListener(eventName, function () {
                dropZone.classList.remove('drag-over');
            }, false);
        });

        dropZone.addEventListener('drop', function (e) {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                handleFileSelection(card, files[0]);
            }
        });

        // Remove file
        if (removeButton) {
            removeButton.addEventListener('click', function (e) {
                e.stopPropagation();
                resetCard(card);
            });
        }

        // Upload button
        uploadButton.addEventListener('click', function () {
            const file = fileInput.files[0];
            if (!file) {
                showResult('error', 'Sin archivo', 'Por favor seleccioná un archivo Excel antes de importar.');
                return;
            }
            uploadFile(card, endpoint, file);
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function handleFileSelection(card, file) {
        if (!file) return;

        const error = validateFile(file);
        if (error) {
            showResult('error', 'Archivo no válido', error);
            resetCard(card);
            return;
        }

        const dropZoneContent = card.querySelector('.drop-zone-content');
        const dropZoneFile = card.querySelector('.drop-zone-file');
        const fileName = card.querySelector('.file-name');
        const fileSize = card.querySelector('.file-size');

        if (dropZoneContent) dropZoneContent.style.display = 'none';
        if (dropZoneFile) dropZoneFile.style.display = 'flex';
        if (fileName) fileName.textContent = file.name;
        if (fileSize) fileSize.textContent = formatFileSize(file.size);

        card.querySelector('.upload-submit').disabled = false;
        hideResult();
    }

    function resetCard(card) {
        const fileInput = card.querySelector('.drop-zone-input');
        const dropZoneContent = card.querySelector('.drop-zone-content');
        const dropZoneFile = card.querySelector('.drop-zone-file');
        const uploadButton = card.querySelector('.upload-submit');

        fileInput.value = '';
        if (dropZoneContent) dropZoneContent.style.display = 'block';
        if (dropZoneFile) dropZoneFile.style.display = 'none';
        uploadButton.disabled = false;
    }

    function validateFile(file) {
        if (!file.name.toLowerCase().endsWith(ALLOWED_EXTENSION)) {
            return 'Solo se permiten archivos Excel (.xlsx).';
        }
        if (file.size > MAX_FILE_SIZE) {
            return 'El archivo excede el límite de 50 MB.';
        }
        return null;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function uploadFile(card, endpoint, file) {
        const uploadButton = card.querySelector('.upload-submit');
        const originalText = uploadButton.innerHTML;

        uploadButton.disabled = true;
        uploadButton.innerHTML = '<i class="ti ti-loader-2 me-2 ti-spin"></i>Importando...';
        hideResult();

        showProgress(file.name);
        const progress = simulateProgress();

        const formData = new FormData();
        formData.append('file', file);

        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token
            },
            body: formData
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { response: response, data: data };
                });
            })
            .then(function (result) {
                progress.complete();
                hideProgress();

                if (result.response.ok) {
                    const message =
                        '✅ ' + (result.data.message || 'Importación exitosa') + '<br>' +
                        '📊 Procesados: ' + (result.data.processed_rows || 0) + '<br>' +
                        '➕ Creados: ' + (result.data.created || 0) + '<br>' +
                        '🔄 Actualizados: ' + (result.data.updated || 0) + '<br>' +
                        '❌ Errores: ' + (result.data.errors || 0);
                    showResult(
                        (result.data.errors || 0) > 0 ? 'warning' : 'success',
                        'Importación completada',
                        message
                    );
                    resetCard(card);
                    loadRecentUploads();
                } else {
                    showResult('error', 'Error en la importación', result.data.error || 'Ocurrió un error desconocido.');
                }
            })
            .catch(function (error) {
                progress.complete();
                hideProgress();
                showResult('error', 'Error de conexión', error.message || 'No se pudo conectar con el servidor.');
            })
            .finally(function () {
                uploadButton.disabled = false;
                uploadButton.innerHTML = originalText;
            });
    }

    function simulateProgress() {
        const steps = [
            { percent: 15, step: 1, delay: 300 },
            { percent: 40, step: 2, delay: 600 },
            { percent: 65, step: 3, delay: 800 },
            { percent: 85, step: 4, delay: 700 }
        ];

        let currentStep = 0;
        let completed = false;

        function runStep() {
            if (completed || currentStep >= steps.length) return;
            const step = steps[currentStep];
            updateProgress(step.percent, step.step);
            currentStep++;
            setTimeout(runStep, step.delay);
        }

        runStep();

        return {
            complete: function () {
                completed = true;
                updateProgress(100, 4, true);
            }
        };
    }

    function showProgress(fileName) {
        if (progressPanel) progressPanel.style.display = 'flex';
        if (progressFileName) progressFileName.textContent = fileName;
        updateProgress(0, 0);
    }

    function hideProgress() {
        setTimeout(function () {
            if (progressPanel) progressPanel.style.display = 'none';
        }, 800);
    }

    function updateProgress(percent, activeStep, markCompleted) {
        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.setAttribute('aria-valuenow', percent);
            progressBar.textContent = percent + '%';
        }

        document.querySelectorAll('.processing-step').forEach(function (step) {
            const stepNumber = parseInt(step.getAttribute('data-step'), 10);
            step.classList.remove('active', 'completed');

            if (stepNumber < activeStep) {
                step.classList.add('completed');
            } else if (stepNumber === activeStep) {
                step.classList.add('active');
            }
        });

        if (markCompleted) {
            document.querySelectorAll('.processing-step').forEach(function (step) {
                step.classList.remove('active');
                step.classList.add('completed');
            });
        }
    }

    function showResult(type, title, message) {
        if (!resultPanel || !resultAlert || !resultTitle || !resultMessage) return;

        resultPanel.style.display = 'flex';
        resultTitle.textContent = title;
        resultMessage.innerHTML = message;

        resultAlert.className = 'alert';
        resultAlert.classList.add('alert-' + type);

        window.scrollTo({ top: resultPanel.offsetTop - 20, behavior: 'smooth' });
    }

    function hideResult() {
        if (resultPanel) resultPanel.style.display = 'none';
    }

    function loadRecentUploads() {
        return fetch('/api/uploads', {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Error cargando importaciones');
                return response.json();
            })
            .then(function (data) {
                renderUploads(data.uploads || []);
            })
            .catch(function (error) {
                console.error('Error cargando importaciones:', error);
            });
    }

    function renderUploads(uploads) {
        const tbody = uploadsTable ? uploadsTable.querySelector('tbody') : null;
        if (!tbody) return;

        tbody.innerHTML = '';

        if (!uploads.length) {
            tbody.innerHTML =
                '<tr class="empty-row">' +
                '<td colspan="5" class="text-center text-secondary py-4">' +
                '<i class="ti ti-inbox me-2"></i>No hay importaciones recientes' +
                '</td></tr>';
            return;
        }

        uploads.slice(0, 10).forEach(function (upload) {
            const statusClass = getStatusClass(upload.status);
            const row = document.createElement('tr');
            row.innerHTML =
                '<td>' + (upload.id || '-') + '</td>' +
                '<td>' + escapeHtml(upload.filename || '-') + '</td>' +
                '<td>' + formatDate(upload.upload_date) + '</td>' +
                '<td>' + (upload.processed_rows || 0) + '</td>' +
                '<td><span class="badge ' + statusClass + '">' + escapeHtml(upload.status || 'unknown') + '</span></td>';
            tbody.appendChild(row);
        });
    }

    function getStatusClass(status) {
        switch ((status || '').toLowerCase()) {
            case 'completed': return 'bg-success text-success-fg';
            case 'processing': return 'bg-warning text-warning-fg';
            case 'failed': return 'bg-danger text-danger-fg';
            default: return 'bg-secondary text-secondary-fg';
        }
    }

    function formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return dateString;
        return date.toLocaleString('es-AR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
