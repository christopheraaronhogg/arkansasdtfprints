// Admin page functionality for pagination and lazy loading

// Apply the default filter (open orders) on page load
function applyDefaultFilter() {
    // Select the "Open" toggle option
    const openOption = document.querySelector('.toggle-option[data-value="open"]');
    
    if (openOption) {
        // Remove active class from any currently active option
        const activeOption = document.querySelector('.toggle-option.active');
        if (activeOption) {
            activeOption.classList.remove('active');
        }
        
        // Add active class to the open option
        openOption.classList.add('active');
        
        // Position the slider
        const options = document.querySelectorAll('.toggle-option');
        const index = Array.from(options).indexOf(openOption);
        const slider = document.querySelector('.toggle-slider');
        
        if (slider) {
            slider.style.transform = `translateX(${index * 100}%)`;
        }
        
        // Clear any filter cache to ensure a clean state
        try {
            sessionStorage.removeItem('adminPaginationPage');
            sessionStorage.removeItem('adminPaginationItemsPerPage');
        } catch (e) {
            console.warn('Failed to clear pagination state', e);
        }
        
        // Apply the filter immediately
        applyFilters();
    }
}

// Apply all filters and update pagination
function applyFilters() {
    const statusFilter = document.querySelector('.toggle-option.active')?.dataset.value || '';
    const startDate = document.getElementById('startDate')?.value || '';
    const endDate = document.getElementById('endDate')?.value || '';
    
    console.log("Active tab:", statusFilter, "Applying filters");
    
    const orderItems = document.querySelectorAll('.order-item');
    let visibleCount = 0;
    
    // First, clear any previous filtering state
    orderItems.forEach(function(item) {
        item.classList.remove('filtered-out');
    });
    
    orderItems.forEach(function(item) {
        const itemStatus = item.dataset.status;
        const itemDate = item.dataset.date;
        
        // Apply status filter
        let statusMatch = true;
        if (statusFilter) {
            if (statusFilter === 'open') {
                statusMatch = itemStatus !== 'completed';
                if (item.classList.contains('order-item-top')) {
                    console.log("Order item:", item.dataset.id, "Status:", itemStatus, "Matches open filter:", statusMatch);
                }
            } else if (statusFilter === 'closed') {
                statusMatch = itemStatus === 'completed';
            } else {
                statusMatch = true; // 'all' option
            }
        }
        
        // Apply date filters
        let dateMatch = true;
        if (startDate && itemDate < startDate) {
            dateMatch = false;
        }
        if (endDate && itemDate > endDate) {
            dateMatch = false;
        }
        
        // Show/hide based on filters
        if (statusMatch && dateMatch) {
            item.classList.remove('filtered-out');
            visibleCount++;
        } else {
            item.classList.add('filtered-out');
        }
    });
    
    // Reset and reinitialize pagination with filtered items
    resetPagination();
}

document.addEventListener('DOMContentLoaded', function() {
    // Lazy loading for images
    initLazyLoading();
    
    // Initialize filters first so pagination will work with filtered items
    initFilters();
    
    // Check if we have a stored view state
    try {
        const savedView = sessionStorage.getItem('adminOrdersView');
        if (savedView) {
            // Find the option with this value
            const targetOption = document.querySelector(`.toggle-option[data-value="${savedView}"]`);
            if (targetOption) {
                // Trigger a click on this option to restore the view
                targetOption.click();
                console.log("Restored saved view:", savedView);
            } else {
                // Apply the "open" filter by default
                applyDefaultFilter();
            }
        } else {
            // Apply the "open" filter by default
            applyDefaultFilter();
        }
    } catch (e) {
        console.warn('Failed to restore view state', e);
        // Apply the "open" filter by default
        applyDefaultFilter();
    }
    
    // Pagination (now works with filtered items)
    initPagination();
    
    // Initialize order selection for bulk actions
    initOrderSelection();
});

// Intersection Observer for lazy loading images
function initLazyLoading() {
    // Check if browser supports Intersection Observer
    if ('IntersectionObserver' in window) {
        const lazyImageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const lazyImage = entry.target;
                    const src = lazyImage.dataset.src;
                    
                    // Create a new image to preload
                    const img = new Image();
                    img.onload = function() {
                        // Only replace src when image is loaded
                        lazyImage.src = src;
                        lazyImage.classList.add('loaded');
                    };
                    img.src = src;
                    
                    // Stop observing after loading
                    lazyImageObserver.unobserve(lazyImage);
                }
            });
        }, {
            rootMargin: '100px 0px',  // Start loading when image is 100px from viewport
            threshold: 0.01
        });

        // Observe all lazy images
        document.querySelectorAll('img.lazy-image').forEach(function(lazyImage) {
            lazyImageObserver.observe(lazyImage);
        });
    } else {
        // Fallback for browsers without Intersection Observer
        loadAllImagesImmediately();
    }
}

// Fallback for older browsers
function loadAllImagesImmediately() {
    const lazyImages = document.querySelectorAll('img.lazy-image');
    lazyImages.forEach(function(lazyImage) {
        lazyImage.src = lazyImage.dataset.src;
        lazyImage.classList.add('loaded');
    });
}

// Pagination functionality
function initPagination() {
    // Get only visible items (not filtered out)
    const orderItems = document.querySelectorAll('.order-item:not(.filtered-out)');
    const totalItems = orderItems.length;
    const itemsPerPage = 20; // Default number of items per page
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    console.log("Initializing pagination:", totalItems, "items,", totalPages, "pages");
    
    // Always create pagination controls (even for small item sets)
    createPaginationControls(totalPages);
    
    // Initialize with first page
    showFilteredPage(1, itemsPerPage, Array.from(orderItems));
    
    // Save pagination state to browser storage
    savePaginationState(1, itemsPerPage);
}

// Create pagination controls
function createPaginationControls(totalPages) {
    // Check if pagination already exists
    const existingPagination = document.querySelector('.pagination-container');
    if (existingPagination) {
        // Update total pages only
        if (document.getElementById('totalPages')) {
            document.getElementById('totalPages').textContent = totalPages || 1;
        }
        return;
    }

    const orderList = document.querySelector('.order-list');
    const paginationContainer = document.createElement('div');
    paginationContainer.className = 'pagination-container mt-4 d-flex justify-content-between align-items-center p-3 bg-light border rounded';
    
    // Create page size selector
    const pageSizeContainer = document.createElement('div');
    pageSizeContainer.className = 'page-size-container d-flex align-items-center';
    pageSizeContainer.innerHTML = `
        <label for="itemsPerPage" class="me-2 fw-bold">Items per page:</label>
        <select id="itemsPerPage" class="form-select" style="width: auto; display: inline-block;">
            <option value="10">10</option>
            <option value="20" selected>20</option>
            <option value="50">50</option>
            <option value="100">100</option>
        </select>
    `;
    
    // Create pages nav
    const pagesContainer = document.createElement('div');
    pagesContainer.className = 'pages-container';
    pagesContainer.innerHTML = `
        <div class="btn-group" role="group" aria-label="Pagination">
            <button type="button" class="btn btn-primary" id="prevPage" disabled>
                <i class="fas fa-chevron-left"></i>
            </button>
            <span class="btn btn-secondary" id="pageInfo">
                Page <span id="currentPage" class="fw-bold">1</span> of <span id="totalPages" class="fw-bold">${totalPages}</span>
            </span>
            <button type="button" class="btn btn-primary" id="nextPage" ${totalPages <= 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-right"></i>
            </button>
        </div>
    `;
    
    paginationContainer.appendChild(pageSizeContainer);
    paginationContainer.appendChild(pagesContainer);
    
    // Add pagination after order list
    orderList.parentNode.insertBefore(paginationContainer, orderList.nextSibling);
    
    // Add event listeners
    document.getElementById('prevPage').addEventListener('click', function() {
        const currentPage = Number(document.getElementById('currentPage').textContent);
        if (currentPage > 1) {
            const itemsPerPage = Number(document.getElementById('itemsPerPage').value);
            const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
            showFilteredPage(currentPage - 1, itemsPerPage, visibleItems);
            savePaginationState(currentPage - 1, itemsPerPage);
        }
    });
    
    document.getElementById('nextPage').addEventListener('click', function() {
        const currentPage = Number(document.getElementById('currentPage').textContent);
        const totalPages = Number(document.getElementById('totalPages').textContent);
        if (currentPage < totalPages) {
            const itemsPerPage = Number(document.getElementById('itemsPerPage').value);
            const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
            showFilteredPage(currentPage + 1, itemsPerPage, visibleItems);
            savePaginationState(currentPage + 1, itemsPerPage);
        }
    });
    
    document.getElementById('itemsPerPage').addEventListener('change', function() {
        const itemsPerPage = Number(this.value);
        const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
        const totalPages = Math.ceil(visibleItems.length / itemsPerPage);
        
        // Reset to page 1 with new page size
        document.getElementById('totalPages').textContent = totalPages || 1;
        showFilteredPage(1, itemsPerPage, visibleItems);
        savePaginationState(1, itemsPerPage);
    });
    
    // Load saved pagination state if exists
    loadPaginationState();
}

// Show specific page with filtered items
function showFilteredPage(pageNumber, itemsPerPage, visibleItems) {
    const startIndex = (pageNumber - 1) * itemsPerPage;
    const endIndex = Math.min(startIndex + itemsPerPage, visibleItems.length);
    
    // Hide all items first
    document.querySelectorAll('.order-item').forEach(item => {
        item.style.display = 'none';
    });
    
    // Show only filtered items for current page
    for (let i = startIndex; i < endIndex; i++) {
        if (visibleItems[i]) {
            visibleItems[i].style.display = 'flex';
        }
    }
    
    // Update pagination UI
    if (document.getElementById('currentPage')) {
        document.getElementById('currentPage').textContent = pageNumber;
    }
    
    // Toggle button states
    if (document.getElementById('prevPage')) {
        document.getElementById('prevPage').disabled = pageNumber === 1;
    }
    
    if (document.getElementById('nextPage')) {
        document.getElementById('nextPage').disabled = pageNumber === Number(document.getElementById('totalPages').textContent);
    }
    
    // Trigger lazy loading for newly visible images
    triggerLazyLoading();
}

// Handle filters and maintain pagination state
function initFilters() {
    // Status toggle
    document.querySelectorAll('.toggle-option').forEach(function(option) {
        option.addEventListener('click', function() {
            const value = this.dataset.value;
            const activeOption = document.querySelector('.toggle-option.active');
            
            if (activeOption) {
                activeOption.classList.remove('active');
            }
            
            this.classList.add('active');
            
            // Position the slider
            const options = document.querySelectorAll('.toggle-option');
            const index = Array.from(options).indexOf(this);
            const slider = document.querySelector('.toggle-slider');
            
            if (slider) {
                slider.style.transform = `translateX(${index * 100}%)`;
            }
            
            // Clear pagination state when changing tabs to force a clean filter
            try {
                sessionStorage.removeItem('adminPaginationPage');
                sessionStorage.removeItem('adminPaginationItemsPerPage');
                
                // Clear any cache related to the current view
                if (typeof sessionStorage.adminOrdersView !== 'undefined') {
                    sessionStorage.removeItem('adminOrdersView');
                }
            } catch (e) {
                console.warn('Failed to clear pagination state', e);
            }
            
            // Store the current view to help with tab state management
            try {
                sessionStorage.setItem('adminOrdersView', value);
            } catch (e) {
                console.warn('Failed to save view state', e);
            }
            
            // Apply filter
            applyFilters();
        });
    });
    
    // Date filters
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (startDateInput && endDateInput) {
        startDateInput.addEventListener('change', applyFilters);
        endDateInput.addEventListener('change', applyFilters);
    }
}

// Reset pagination after filters change
function resetPagination() {
    // Get only visible items after filtering
    const statusFilter = document.querySelector('.toggle-option.active')?.dataset.value || '';
    const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
    const itemsPerPage = Number(document.getElementById('itemsPerPage')?.value || 20);
    const totalPages = Math.ceil(visibleItems.length / itemsPerPage);
    
    console.log("Active tab:", statusFilter, "Visible items:", visibleItems.length);
    
    // Update total pages
    if (document.getElementById('totalPages')) {
        document.getElementById('totalPages').textContent = totalPages || 1;
    }
    
    // Show first page of filtered results
    if (visibleItems.length > 0) {
        showFilteredPage(1, itemsPerPage, visibleItems);
    } else {
        // No results message
        showNoResultsMessage();
    }
}

// Trigger lazy loading check manually
function triggerLazyLoading() {
    // Force recalculation of Intersection Observer
    window.dispatchEvent(new Event('scroll'));
}

// Save pagination state to session storage
function savePaginationState(currentPage, itemsPerPage) {
    try {
        sessionStorage.setItem('adminPaginationPage', currentPage.toString());
        sessionStorage.setItem('adminPaginationItemsPerPage', itemsPerPage.toString());
    } catch (e) {
        console.warn('Failed to save pagination state', e);
    }
}

// Load pagination state from session storage
function loadPaginationState() {
    try {
        const savedPage = sessionStorage.getItem('adminPaginationPage');
        const savedItemsPerPage = sessionStorage.getItem('adminPaginationItemsPerPage');
        
        if (savedItemsPerPage) {
            const itemsPerPageSelect = document.getElementById('itemsPerPage');
            if (itemsPerPageSelect) {
                itemsPerPageSelect.value = savedItemsPerPage;
                
                // Dispatch change event to update page size - but don't trigger recursion
                try {
                    const event = new Event('change', { bubbles: true });
                    itemsPerPageSelect.dispatchEvent(event);
                } catch (err) {
                    console.warn('Could not dispatch change event:', err);
                }
            }
        }
        
        if (savedPage) {
            const currentPage = Number(savedPage);
            const itemsPerPage = Number(savedItemsPerPage || 
                (document.getElementById('itemsPerPage')?.value || 20));
            const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
            
            // Check if we have enough pages to go to the saved page
            const totalPages = Math.ceil(visibleItems.length / itemsPerPage);
            const validPage = Math.min(currentPage, totalPages || 1);
            
            if (validPage > 0) {
                showFilteredPage(validPage, itemsPerPage, visibleItems);
            }
        }
    } catch (e) {
        console.warn('Failed to load pagination state', e);
    }
}

// Show message when no results match filters
function showNoResultsMessage() {
    const orderList = document.querySelector('.order-list');
    
    // Remove existing message if any
    const existingMessage = document.querySelector('.no-results-message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Create and insert message
    const messageElement = document.createElement('div');
    messageElement.className = 'no-results-message alert alert-info mt-3';
    messageElement.innerHTML = '<i class="fas fa-info-circle me-2"></i>No orders match your current filters. Try adjusting your filter criteria.';
    
    orderList.parentNode.insertBefore(messageElement, orderList.nextSibling);
}

// Clear all filters
function clearFilters() {
    // Reset status toggle
    const allOption = document.querySelector('.toggle-option[data-value=""]');
    if (allOption) {
        const activeOption = document.querySelector('.toggle-option.active');
        if (activeOption) {
            activeOption.classList.remove('active');
        }
        allOption.classList.add('active');
        
        // Reset slider position
        const options = document.querySelectorAll('.toggle-option');
        const index = Array.from(options).indexOf(allOption);
        const slider = document.querySelector('.toggle-slider');
        if (slider) {
            slider.style.transform = `translateX(${index * 100}%)`;
        }
    }
    
    // Reset date inputs
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (startDateInput) startDateInput.value = '';
    if (endDateInput) endDateInput.value = '';
    
    // Show all items
    document.querySelectorAll('.order-item').forEach(function(item) {
        item.classList.remove('filtered-out');
    });
    
    // Reset pagination
    resetPagination();
}

// For the image previewing functionality
function showFullSizePreview(imgElement) {
    const modal = document.getElementById('previewModal');
    const modalImg = document.getElementById('modalImage');
    const loadingSpinner = document.getElementById('modalLoading');
    
    if (modal && modalImg) {
        // Show modal and loading spinner
        modal.style.display = 'flex';
        if (loadingSpinner) loadingSpinner.style.display = 'flex';
        modalImg.style.display = 'none';
        
        // Get full size image URL from data attribute
        const fullImageUrl = imgElement.getAttribute('data-full-image');
        
        // Create new image to preload
        const img = new Image();
        img.onload = function() {
            // Hide loading spinner and show image when loaded
            if (loadingSpinner) loadingSpinner.style.display = 'none';
            modalImg.src = fullImageUrl;
            modalImg.style.display = 'block';
        };
        img.onerror = function() {
            // Handle error
            if (loadingSpinner) {
                loadingSpinner.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error loading image';
            }
        };
        img.src = fullImageUrl;
    }
}

function closePreviewModal() {
    const modal = document.getElementById('previewModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Initialize order selection for bulk actions
function initOrderSelection() {
    const orderCheckboxes = document.querySelectorAll('.order-checkbox');
    const bulkActions = document.querySelector('.bulk-actions');
    const selectedCountElement = document.getElementById('selectedCount');
    
    if (!orderCheckboxes.length || !bulkActions || !selectedCountElement) return;
    
    // Add event listener to each checkbox
    orderCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', updateSelectedCount);
    });
    
    // Update selected count and toggle bulk actions visibility
    function updateSelectedCount() {
        const selectedCount = document.querySelectorAll('.order-checkbox:checked').length;
        selectedCountElement.textContent = `${selectedCount} selected`;
        
        // Show/hide bulk actions section
        if (selectedCount > 0) {
            bulkActions.style.display = 'block';
        } else {
            bulkActions.style.display = 'none';
        }
    }
}