// Function to manage loading state
const LoadingManager = {
    show(message = 'Uploading files...', progress = 0) {
        // Create progress container if it doesn't exist
        let container = document.getElementById('progress-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'progress-container';
            container.innerHTML = `
                <div class="progress" role="progressbar">
                    <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%">
                        <div id="progress-text">0%</div>
                    </div>
                </div>
                <div class="progress-status"></div>
            `;

            // Insert after email-submit-row
            const emailSubmitRow = document.querySelector('.email-submit-row');
            emailSubmitRow.parentNode.insertBefore(container, emailSubmitRow.nextSibling);

            // Force a reflow before adding the show class
            container.offsetHeight;
        }

        // Show the container with animation
        requestAnimationFrame(() => {
            container.classList.add('show');
        });

        // Update progress
        this.updateProgress(progress, message);
    },

    updateProgress(progress, message = '') {
        const container = document.getElementById('progress-container');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');

        if (progressBar && progressText) {
            // Round progress to nearest integer
            const roundedProgress = Math.round(progress);

            // Update progress bar width and text
            progressBar.style.width = `${roundedProgress}%`;
            progressText.textContent = `${roundedProgress}%`;

            // Add progress to data attribute for CSS styling
            progressBar.setAttribute('data-progress', `${roundedProgress}%`);

            // Update status message if provided
            if (message) {
                const statusDiv = document.querySelector('.progress-status');
                if (statusDiv) {
                    statusDiv.textContent = message;
                }
            }

            // Add animation class when progress is increasing
            if (roundedProgress > 0) {
                progressBar.classList.add('progress-bar-animated');
            } else {
                progressBar.classList.remove('progress-bar-animated');
            }
        }
    },

    hide() {
        const container = document.getElementById('progress-container');
        if (container) {
            container.classList.remove('show');
            // Remove the container after animation
            setTimeout(() => {
                container.remove();
            }, 300);
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
        // Custom rounding function that rounds up at .5
        function roundUpAtHalf(num) {
            // Convert to string with 2 decimal places for display and calculation
            const displayValue = Number(num).toFixed(2);
            console.log('Display value:', displayValue);

            // Parse back to number and round for pricing
            const value = parseFloat(displayValue);
            const rounded = (value % 1 >= 0.5) ? Math.ceil(value) : Math.round(value);
            console.log('Rounded value:', rounded);
            return Math.max(1, rounded);
        }

        console.log('Raw dimensions:', { width, height });

        // Round to nearest inch with minimum of 1 inch, rounding up at .5
        const roundedWidth = roundUpAtHalf(width);
        const roundedHeight = roundUpAtHalf(height);
        const area = roundedWidth * roundedHeight;
        const cost = area * state.basePrice * quantity;

        console.log('Cost calculation:', {
            originalWidth: width,
            originalHeight: height,
            displayWidth: Number(width).toFixed(2),
            displayHeight: Number(height).toFixed(2),
            roundedWidth,
            roundedHeight,
            area,
            basePrice: state.basePrice,
            quantity,
            finalCost: cost
        });

        return cost;
    }

    return {
        addImage(file, img, dimensions) {
            const id = crypto.randomUUID();

            // Use the physical dimensions from the server
            const width_inches = dimensions.width;
            const height_inches = dimensions.height;

            state.images.set(id, {
                file,
                original: {
                    width: width_inches,
                    height: height_inches,
                    aspect: width_inches / height_inches
                },
                current: {
                    width: width_inches,
                    height: height_inches
                },
                quantity: 1,
                notes: '',
                get cost() {
                    // Use the current dimensions that are being displayed
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

            // Update the other dimension based on aspect ratio
            const otherDimension = dimension === 'width' ? 'height' : 'width';
            let otherValue;

            if (dimension === 'width') {
                // If width changed, calculate new height
                otherValue = newValue / imageState.original.aspect;
            } else {
                // If height changed, calculate new width
                otherValue = newValue * imageState.original.aspect;
            }

            imageState.current[otherDimension] = Math.max(0.1, parseFloat(otherValue.toFixed(2)));
        },

        updateQuantity(id, quantity) {
            const imageState = state.images.get(id);
            if (!imageState) return;

            imageState.quantity = Math.max(1, parseInt(quantity) || 1);
        },

        updateNotes(id, notes) {
            const imageState = state.images.get(id);
            if (!imageState) return;
            imageState.notes = notes;
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
        },

        removeImage(id) {
            return state.images.delete(id);
        },

        hasImages() {
            return state.images.size > 0;
        }
    };
})();

// UI MANAGEMENT
const PrintUI = {
    init() {
        this.form = document.getElementById('upload-form');
        this.dropZone = document.getElementById('dropZone');
        this.fileInput = document.getElementById('file-input');
        this.imagesContainer = document.getElementById('images-container');
        if (this.imagesContainer) {
            this.imagesContainer.className = 'images-grid';
        }
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

            // Update the file input with the dropped files
            const dataTransfer = new DataTransfer();
            files.forEach(file => dataTransfer.items.add(file));
            this.fileInput.files = dataTransfer.files;

            await this.handleFiles(files);
        });

        this.fileInput.addEventListener('change', async () => {
            const files = [...this.fileInput.files].filter(f => f.type === 'image/png');
            await this.handleFiles(files);
        });

        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (PrintCalculator.hasImages()) {
                this.handleSubmit();
            } else {
                this.showAlert('Please add at least one image to your order', 'error');
            }
        });

        // Add email input Enter key handler
        const emailInput = document.querySelector('input[name="email"]');
        if (emailInput) {
            emailInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (PrintCalculator.hasImages()) {
                        this.handleSubmit();
                    } else {
                        this.showAlert('Please add at least one image to your order', 'error');
                    }
                }
            });
        }

        // Add PO number input Enter key handler
        const poInput = document.querySelector('input[name="po_number"]');
        if (poInput) {
            poInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (PrintCalculator.hasImages()) {
                        this.handleSubmit();
                    } else {
                        this.showAlert('Please add at least one image to your order', 'error');
                    }
                }
            });
        }
    },

    loadImage(file) {
        return new Promise((resolve, reject) => {
            // First get the physical dimensions from the server
            const formData = new FormData();
            formData.append('file', file);

            fetch('/get-dimensions', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(dimensions => {
                    const img = new Image();
                    img.onload = () => resolve({ img, dimensions });
                    img.onerror = reject;
                    img.src = URL.createObjectURL(file);
                })
                .catch(reject);
        });
    },

    async handleFiles(files) {
        let successCount = 0;
        let errorCount = 0;

        for (const file of files) {
            try {
                const { img, dimensions } = await this.loadImage(file);
                const id = PrintCalculator.addImage(file, img, dimensions);
                this.renderImagePreview(id, img);
                this.updateTotalDisplay();
                successCount++;
            } catch (error) {
                console.error('Error processing image:', error);
                errorCount++;
                this.showAlert(`Failed to process ${file.name}: ${error.message}`, 'error');
            }
        }

        // Show summary toast for successful uploads
        if (successCount > 0) {
            this.showAlert(
                `Successfully added ${successCount} image${successCount !== 1 ? 's' : ''} to your order`,
                'success'
            );
        }
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
        const imageState = PrintCalculator.getImageState(id);
        if (!imageState) return;

        const container = document.createElement('div');
        container.className = 'size-inputs';
        container.dataset.imageId = id;

        container.innerHTML = `
            <div class="preview-content">
                <div class="preview-section">
                    <button class="delete-btn" title="Remove image">
                        <i class="fas fa-times"></i>
                    </button>
                    <img src="${img.src}" class="preview-image" alt="Preview">
                </div>
                <div class="controls-section">
                    <div class="info-row">
                        <div class="quantity-size-container">
                            <div class="quantity-input">
                                <label>Qty:</label>
                                <input type="number" class="quantity" value="${imageState.quantity}" min="1">
                            </div>
                            <div class="size-display">
                                <span class="dimensions">${imageState.current.width.toFixed(1)}" × ${imageState.current.height.toFixed(1)}"</span>
                            </div>
                        </div>
                    </div>
                    <div class="notes-input">
                        <label>Notes:</label>
                        <textarea class="notes" placeholder="Add any special instructions...">${imageState.notes}</textarea>
                    </div>
                    <div class="cost-display">
                        <span class="cost-label">Cost:</span>
                        <span class="cost-value">$${imageState.cost.toFixed(2)}</span>
                    </div>
                </div>
            </div>`;

        document.getElementById('images-container').appendChild(container);

        // Add quantity input handler
        container.querySelector('.quantity').addEventListener('input', (e) => {
            this.handleQuantityInput(e.target);
        });

        // Add notes input handler
        container.querySelector('.notes').addEventListener('input', (e) => {
            const id = container.dataset.imageId;
            PrintCalculator.updateNotes(id, e.target.value);
        });

        // Add delete button handler
        container.querySelector('.delete-btn').addEventListener('click', (e) => {
            // Prevent the event from bubbling up to the form
            e.preventDefault();
            e.stopPropagation();

            // Remove from state
            PrintCalculator.removeImage(id);

            // Remove the container with animation
            container.style.opacity = '0';
            container.style.transform = 'scale(0.95)';

            setTimeout(() => {
                container.remove();
                this.updateTotalDisplay();

                // Show feedback toast
                this.showAlert('Image removed from order', 'success');

                // If no images left, reset the form
                if (!PrintCalculator.hasImages()) {
                    this.form.reset();
                }
            }, 300);
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
        const total = PrintCalculator.getTotalCost();
        const formattedTotal = `$${total.toFixed(2)}`;

        // Update the total cost display if it exists
        const totalDisplay = document.getElementById('totalCost');
        if (totalDisplay) {
            totalDisplay.textContent = `Total: ${formattedTotal}`;
        }

        // Update the submit button total
        const submitBtn = document.querySelector('.submit-btn');
        if (submitBtn) {
            submitBtn.setAttribute('data-total', formattedTotal);
        }
    },

    async handleSubmit() {
        try {
            const formData = new FormData(this.form);
            const orderDetails = [];
            const files = [];

            // Collect files and details
            document.querySelectorAll('.size-inputs').forEach((container) => {
                const id = container.dataset.imageId;
                const imageState = PrintCalculator.getImageState(id);
                if (imageState) {
                    files.push(imageState.file);
                    const details = {
                        width: imageState.current.width,
                        height: imageState.current.height,
                        quantity: imageState.quantity,
                        cost: imageState.cost,
                        filename: imageState.file.name,
                        notes: imageState.notes
                    };
                    orderDetails.push(details);
                }
            });

            LoadingManager.show('Creating your order...', 0);

            // First create the order
            const orderFormData = new FormData();
            orderFormData.append('email', formData.get('email'));
            orderFormData.append('po_number', formData.get('po_number'));
            orderFormData.append('orderDetails', JSON.stringify(orderDetails));
            orderFormData.append('totalCost', PrintCalculator.getTotalCost());

            try {
                const response = await fetch('/create-order', {
                    method: 'POST',
                    body: orderFormData
                });

                if (!response.ok) {
                    const result = await response.json();
                    throw new Error(result.details || 'Failed to create order');
                }

                const orderResult = await response.json();
                const orderId = orderResult.order_id;

                // Upload files one by one
                const uploadedFiles = [];
                for (let i = 0; i < files.length; i++) {
                    const file = files[i];

                    // Check individual file size
                    if (file.size > 32 * 1024 * 1024) { // 32MB limit per file
                        this.showAlert(
                            `File ${file.name} is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum allowed size per file is 32MB`,
                            'error'
                        );
                        LoadingManager.hide();
                        return;
                    }

                    const singleFormData = new FormData();

                    // Add the current file
                    singleFormData.append('file', file);
                    singleFormData.append('order_id', orderId);
                    singleFormData.append('fileDetails', JSON.stringify(orderDetails[i]));

                    // Mark if this is the last file
                    if (i === files.length - 1) {
                        singleFormData.append('is_last_file', 'true');
                    }

                    // Update progress
                    const progress = ((i + 1) / files.length) * 100;
                    LoadingManager.show(`Uploading file ${i + 1} of ${files.length}: ${file.name}`, progress);

                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            body: singleFormData,
                            signal: AbortSignal.timeout(30000), // 30 second timeout per file
                            headers: {
                                'Connection': 'keep-alive'
                            }
                        });

                        if (!response.ok) {
                            const result = await response.json();
                            throw new Error(result.details || 'Upload failed');
                        }

                        const result = await response.json();
                        if (result.success) {
                            uploadedFiles.push(file.name);
                        } else {
                            throw new Error(result.error || 'Upload failed');
                        }
                    } catch (error) {
                        if (error.name === 'AbortError') {
                            this.showAlert(
                                `Upload timed out for file ${file.name}. Please try again.`,
                                'error'
                            );
                        } else {
                            this.showAlert(
                                `Failed to upload ${file.name}: ${error.message}`,
                                'error'
                            );
                        }
                        LoadingManager.hide();
                        return;
                    }
                }

                // All files uploaded successfully
                LoadingManager.updateProgress(100, 'Upload complete!');
                this.showAlert(
                    `Successfully uploaded ${uploadedFiles.length} files! Check your email for confirmation.`,
                    'success'
                );

                // Add a small delay before redirecting
                await new Promise(resolve => setTimeout(resolve, 1000));
                window.location.href = '/success';

            } catch (error) {
                console.error('Fatal error:', error);
                this.showAlert(
                    `An unexpected error occurred: ${error.message}. Please try again or contact support if the issue persists.`,
                    'error'
                );
            }
        } finally {
            LoadingManager.hide();
        }
    },

    showAlert(message, type = 'error') {
        console.log('Showing alert:', { message, type }); // Debug log

        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            toastContainer.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 99999;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            `;
            document.body.appendChild(toastContainer);
            console.log('Created toast container'); // Debug log
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type === 'error' ? 'toast-error' : 'toast-success'}`;
        toast.style.cssText = `
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            padding: 12px 16px;
            min-width: 300px;
            max-width: 400px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transform: translateX(120%);
            transition: transform 0.3s ease;
            pointer-events: auto;
            border-left: 4px solid ${type === 'error' ? '#ef4444' : '#22c55e'};
        `;

        // Add icon based on type
        const icon = type === 'error' ? 'exclamation-circle' : 'check-circle';

        toast.innerHTML = `
            <div class="toast-content" style="display: flex; align-items: center; gap: 12px; flex: 1;">
                <i class="fas fa-${icon} toast-icon" style="color: ${type === 'error' ? '#ef4444' : '#22c55e'}; font-size: 1.2rem;"></i>
                <span class="toast-message" style="font-size: 0.95rem; color: #1e293b; line-height: 1.4;">${message}</span>
            </div>
            <button class="toast-close" style="background: none; border: none; padding: 4px; margin-left: 8px; cursor: pointer; color: #64748b; opacity: 0.7;">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Add to container
        toastContainer.appendChild(toast);
        console.log('Added toast to container'); // Debug log

        // Add click handler to close button
        toast.querySelector('.toast-close').onclick = () => {
            toast.style.transform = 'translateX(120%)';
            setTimeout(() => toast.remove(), 300);
        };

        // Auto remove after 5 seconds for success, stay for error
        if (type !== 'error') {
            setTimeout(() => {
                toast.style.transform = 'translateX(120%)';
                setTimeout(() => toast.remove(), 300);
            }, 5000);
        }

        // Force a reflow to ensure the animation works
        toast.offsetHeight;

        // Animate in
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            console.log('Animated toast in'); // Debug log
        });
    },

    handleDimensionChange(event, imageId) {
        const input = event.target;
        const value = parseFloat(input.value) || 0;
        const dimension = input.dataset.dimension;

        PrintCalculator.updateImageDimension(imageId, dimension, value);
        this.updateTotalDisplay();
    }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', () => PrintUI.init());