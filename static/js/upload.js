// STATE & CORE LOGIC
const PrintCalculator = (() => {
    const state = {
        images: new Map(),
        basePrice: 0.02, // price per square inch
    };

    function calculateCost(width, height, quantity = 1) {
        const roundedWidth = Math.round(width);
        const roundedHeight = Math.round(height);
        const area = roundedWidth * roundedHeight;
        return area * state.basePrice * quantity;
    }

    return {
        addImage(file, img) {
            const id = crypto.randomUUID();
            const DPI = 300;
            const maxWidth = 24 * DPI;
            const maxHeight = 24 * DPI;
            const scale = Math.min(maxWidth / img.naturalWidth, maxHeight / img.naturalHeight, 1);
            const finalWidth = (img.naturalWidth * scale) / DPI;
            const finalHeight = (img.naturalHeight * scale) / DPI;

            state.images.set(id, {
                file,
                original: {
                    width: finalWidth,
                    height: finalHeight,
                    aspect: finalWidth / finalHeight
                },
                current: {
                    width: finalWidth,
                    height: finalHeight
                },
                quantity: 1,
                get cost() {
                    return calculateCost(
                        this.current.width,
                        this.current.height,
                        this.quantity
                    );
                }
            });

            return id;
        },

        updateDimension(id, dimension, value) {
            const imageState = state.images.get(id);
            if (!imageState) return;

            const newValue = parseFloat(value);
            if (isNaN(newValue)) return;

            // Update the specified dimension
            imageState.current[dimension] = Math.max(0.1, parseFloat(newValue.toFixed(2)));

            // Update the other dimension to maintain aspect ratio
            const otherDimension = dimension === 'width' ? 'height' : 'width';
            const otherValue = imageState.current[dimension] / imageState.original.aspect;
            imageState.current[otherDimension] = Math.max(0.1, parseFloat(otherValue.toFixed(2)));
        },

        updateQuantity(id, quantity) {
            const imageState = state.images.get(id);
            if (!imageState) return;

            imageState.quantity = Math.max(1, parseInt(quantity) || 1);
        },

        getImageState(id) {
            return state.images.get(id);
        },

        getImageCost(id) {
            const imageState = state.images.get(id);
            return imageState ? imageState.cost : 0;
        },

        getTotalCost() {
            let total = 0;
            state.images.forEach(img => {
                total += img.cost;
            });
            return total;
        }
    };
})();

// UI MANAGEMENT
const PrintUI = {
    init() {
        this.form = document.getElementById('upload-form');
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('file-input');
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

        this.dropZone.addEventListener('drop', async (e) => {
            e.preventDefault();
            this.dropZone.classList.remove('dragover');

            const files = [...e.dataTransfer.files].filter(f => f.type === 'image/png');
            await this.handleFiles(files);
        });

        this.fileInput.addEventListener('change', async () => {
            const files = [...this.fileInput.files].filter(f => f.type === 'image/png');
            await this.handleFiles(files);
        });

        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
    },

    loadImage(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    },

    async handleFiles(files) {
        for (const file of files) {
            try {
                const img = await this.loadImage(file);
                const id = PrintCalculator.addImage(file, img);
                this.renderImagePreview(id, img);
                this.updateTotalDisplay();
            } catch (error) {
                console.error('Error processing image:', error);
            }
        }
    },

    handleDimensionInput(input) {
        const container = input.closest('.size-inputs');
        const id = container.dataset.imageId;
        const dimension = input.classList.contains('width-input') ? 'width' : 'height';

        PrintCalculator.updateDimension(id, dimension, input.value);
        const imageState = PrintCalculator.getImageState(id);

        // Update linked dimension input
        const otherDimension = dimension === 'width' ? 'height' : 'width';
        const otherInput = container.querySelector(
            `.${otherDimension}-input`
        );
        otherInput.value = imageState.current[otherDimension].toFixed(2);

        // Update costs
        this.updateCostDisplay(id);
        this.updateTotalDisplay();
    },

    handleQuantityInput(input) {
        const container = input.closest('.size-inputs');
        const id = container.dataset.imageId;
        PrintCalculator.updateQuantity(id, input.value);
        this.updateCostDisplay(id);
        this.updateTotalDisplay();
    },

    updateCostDisplay(id) {
        const container = document.querySelector(`[data-image-id="${id}"]`);
        const costValue = container.querySelector('.cost-value');
        if (costValue) {
            costValue.textContent = `$${PrintCalculator.getImageCost(id).toFixed(2)}`;
        }
    },

    renderImagePreview(id, img) {
        const container = document.createElement('div');
        container.className = 'size-inputs';
        container.dataset.imageId = id;

        const imageState = PrintCalculator.getImageState(id);

        container.innerHTML = `
            <div class="preview-content">
                <div class="preview-section">
                    <img src="${img.src}" class="preview-image" alt="Preview">
                </div>
                <div class="controls-section">
                    <div class="input-with-unit">
                        <label>Width</label>
                        <input type="number" 
                               value="${imageState.current.width.toFixed(2)}" 
                               step="0.01" 
                               min="0.1" 
                               class="width-input">
                        <span class="unit">in</span>
                    </div>
                    <div class="input-with-unit">
                        <label>Height</label>
                        <input type="number" 
                               value="${imageState.current.height.toFixed(2)}" 
                               step="0.01" 
                               min="0.1" 
                               class="height-input">
                        <span class="unit">in</span>
                    </div>
                    <div class="input-with-unit">
                        <label>Qty</label>
                        <input type="number" 
                               value="${imageState.quantity}" 
                               min="1" 
                               step="1" 
                               class="quantity-input">
                    </div>
                </div>
            </div>
            <div class="cost-display">
                <span>Cost: </span>
                <span class="cost-value">$${imageState.cost.toFixed(2)}</span>
            </div>`;

        document.getElementById('images-container').appendChild(container);

        // Add event listeners to input fields
        container.querySelectorAll('input').forEach(input => {
            input.addEventListener('input', () => {
                if (input.classList.contains('width-input') || input.classList.contains('height-input')) {
                    this.handleDimensionInput(input);
                } else if (input.classList.contains('quantity-input')) {
                    this.handleQuantityInput(input);
                }
            });
        });

        // Add click handler to preview images
        container.querySelector('.preview-image').addEventListener('click', () => this.showFullSizePreview(img.src));
    },

    showFullSizePreview(src) {
        const modal = document.getElementById('previewModal');
        const modalImg = document.getElementById('modalImage');
        modalImg.src = src;
        modal.style.display = 'flex';

        // Close modal handlers
        modal.querySelector('.close-modal').onclick = () => {
            modal.style.display = 'none';
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        };
    },

    updateTotalDisplay() {
        this.totalDisplay.textContent =
            `Total: $${PrintCalculator.getTotalCost().toFixed(2)}`;
    },

    async handleSubmit() {
        const formData = new FormData(this.form);
        const orderDetails = [];

        // Add all image details
        document.querySelectorAll('.size-inputs').forEach((container) => {
            const id = container.dataset.imageId;
            const imageState = PrintCalculator.getImageState(id);
            if (imageState) {
                formData.append('files[]', imageState.file);
                orderDetails.push({
                    width: imageState.current.width,
                    height: imageState.current.height,
                    quantity: imageState.quantity,
                    cost: imageState.cost
                });
            }
        });

        formData.append('orderDetails', JSON.stringify(orderDetails));
        formData.append('totalCost', PrintCalculator.getTotalCost());

        try {
            // Get the current URL's origin to build the absolute URL
            const origin = window.location.origin;
            const response = await fetch(`${origin}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    const data = await response.json();
                    throw new Error(data.error || 'Failed to submit order');
                } else {
                    throw new Error(`Server error: ${response.status}`);
                }
            }

            const data = await response.json();

            // Show success message and reset form
            this.showAlert('Order successfully submitted! Check your email for confirmation.', 'success');
            this.form.reset();
            document.getElementById('images-container').innerHTML = '';
            this.totalDisplay.textContent = 'Total: $0.00';

        } catch (error) {
            console.error('Submission error:', error);
            this.showAlert(error.message || 'Failed to submit order. Please try again.', 'error');
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