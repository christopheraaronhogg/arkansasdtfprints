// STATE & CORE LOGIC
const PrintCalculator = (() => {
    const state = {
        basePrice: 5.00,
        pricePerSqInch: 0.15
    };

    function calculateCost(width, height) {
        const area = width * height;
        return state.basePrice + (area * state.pricePerSqInch);
    }

    return { calculateCost };
})();

// UI MANAGEMENT
const PrintUI = {
    init() {
        this.form = document.getElementById('upload-form');
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('file-input');
        this.preview = document.getElementById('image-preview');
        this.totalDisplay = document.getElementById('totalCost');
        this.setupEventListeners();
    },

    setupEventListeners() {
        this.dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.dropZone.classList.add('dragover');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('dragover');
        });

        this.dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) { // Allow other image types
                this.fileInput.files = e.dataTransfer.files;
                this.handleFile(file);
            }
        });

        this.fileInput.addEventListener('change', () => {
            const file = this.fileInput.files[0];
            if (file) {
                this.handleFile(file);
            }
        });

        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
    },

    handleFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                // Convert pixels to inches (300 DPI)
                const widthInches = (img.width / 300).toFixed(2);
                const heightInches = (img.height / 300).toFixed(2);
                const cost = PrintCalculator.calculateCost(widthInches, heightInches);

                this.renderPreview(e.target.result, widthInches, heightInches, cost);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    },

    renderPreview(imgSrc, width, height, cost) {
        const container = document.getElementById('images-container');
        container.innerHTML = `
            <div class="preview-content">
                <div class="preview-section">
                    <img src="${imgSrc}" class="preview-image" alt="Preview">
                </div>
                <div class="info-container">
                    <p>Dimensions: ${width}" × ${height}"</p>
                    <p>Estimated Cost: $${cost.toFixed(2)}</p>
                </div>
            </div>`;

        this.totalDisplay.textContent = `Total: $${cost.toFixed(2)}`;

        // Setup modal preview
        const previewImage = container.querySelector('.preview-image');
        const modal = document.getElementById('previewModal');
        const modalImg = document.getElementById('modalImage');
        const closeBtn = document.querySelector('.close-modal');

        previewImage.onclick = () => {
            modal.style.display = 'flex';
            modalImg.src = imgSrc;
        };

        closeBtn.onclick = () => {
            modal.style.display = 'none';
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        };
    },

    async handleSubmit() {
        const formData = new FormData(this.form);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            // Show success message and reset form
            this.showAlert('Order successfully submitted! Check your email for confirmation.', 'success');
            this.form.reset();
            document.getElementById('images-container').innerHTML = '';
            this.totalDisplay.textContent = 'Total: $0.00';

        } catch (error) {
            this.showAlert(error.message, 'error');
        }
    },

    showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;

        this.form.insertAdjacentElement('beforebegin', alertDiv);

        setTimeout(() => alertDiv.remove(), 5000);
    }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', () => PrintUI.init());