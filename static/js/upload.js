// Function to manage loading state
const LoadingManager = {
    show(message = 'Uploading files...', progress = 0) {
        const spinner = document.createElement('div');
        spinner.id = 'uploadSpinner';
        spinner.innerHTML = `
            <div class="loading-overlay">
                <div class="upload-progress">
                    <div class="progress" style="width: 300px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" 
                             style="width: ${progress}%" 
                             aria-valuenow="${progress}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            ${progress}%
                        </div>
                    </div>
                    <p class="mt-2">${message}</p>
                </div>
            </div>`;
        document.body.appendChild(spinner);
    },

    updateProgress(progress, message) {
        const overlay = document.getElementById('uploadSpinner');
        if (overlay) {
            const progressBar = overlay.querySelector('.progress-bar');
            const messageText = overlay.querySelector('p');
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
                progressBar.textContent = `${progress}%`;
            }
            if (messageText) {
                messageText.textContent = message;
            }
        }
    },

    hide() {
        const spinner = document.getElementById('uploadSpinner');
        if (spinner) {
            spinner.remove();
        }
    }
};

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
        LoadingManager.show('Preparing files for upload...', 0);
        const formData = new FormData(this.form);
        const orderDetails = [];

        // Add all image details
        document.querySelectorAll('.size-inputs').forEach((container) => {
            const id = container.dataset.imageId;
            const imageState = PrintCalculator.getImageState(id);
            if (imageState) {
                formData.append('file', imageState.file);
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

        let retryCount = 0;
        const maxRetries = 3;

        while (retryCount < maxRetries) {
            try {
                LoadingManager.updateProgress(30, `Uploading files to server... (Attempt ${retryCount + 1})`);
                const origin = window.location.origin;
                const response = await fetch(`${origin}/upload`, {
                    method: 'POST',
                    body: formData
                });

                LoadingManager.updateProgress(60, 'Processing your order...');

                const data = await response.json();

                if (!response.ok) {
                    const errorMessage = data.details || data.error || 'Failed to submit order';
                    throw new Error(errorMessage);
                }

                LoadingManager.updateProgress(100, 'Order submitted successfully!');

                // Show success message and handle redirect
                this.showAlert(data.message || 'Order successfully submitted! Check your email for confirmation.', 'success');

                // If there's a redirect URL, navigate to it after a short delay
                if (data.redirect) {
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 1000);
                } else {
                    // If no redirect, just reset the form
                    this.form.reset();
                    document.getElementById('images-container').innerHTML = '';
                    this.totalDisplay.textContent = 'Total: $0.00';
                }
                break; // Exit retry loop on success

            } catch (error) {
                retryCount++;
                console.error('Submission error:', error);

                if (retryCount === maxRetries) {
                    this.showAlert(
                        error.message || 'Failed to submit order after multiple attempts. Please try again later.',
                        'error'
                    );
                    break;
                }

                // Show retry message
                LoadingManager.updateProgress(
                    30,
                    `Upload failed. Retrying... (Attempt ${retryCount + 1}/${maxRetries})`
                );

                // Wait before retrying
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        }

        LoadingManager.hide();
    },

    showAlert(message, type = 'error') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Remove any existing alerts
        const existingAlerts = document.querySelectorAll('.alert');
        existingAlerts.forEach(alert => alert.remove());

        // Insert the new alert at the top of the form
        this.form.insertAdjacentElement('beforebegin', alertDiv);

        // Remove the alert after 5 seconds if it's a success message
        if (type === 'success') {
            setTimeout(() => alertDiv.remove(), 5000);
        }
    }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', () => PrintUI.init());