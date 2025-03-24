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
        
        // Initialize filter state with 'open'
        filterState.statusFilter = 'open';
        
        // Apply the filter immediately
        applyFilters();
    }
}

// Single source of truth for current filter state
const filterState = {
    statusFilter: '',
    startDate: '',
    endDate: '',
    // Call this to update the filter state from the DOM
    updateFromDOM: function() {
        this.statusFilter = document.querySelector('.toggle-option.active')?.dataset.value || '';
        this.startDate = document.getElementById('startDate')?.value || '';
        this.endDate = document.getElementById('endDate')?.value || '';
        console.log("Filter state updated:", this.statusFilter, this.startDate, this.endDate);
        return this;
    }
};

// Apply all filters and update pagination
function applyFilters() {
    // Update filter state from DOM
    filterState.updateFromDOM();
    
    console.log("Active tab:", filterState.statusFilter, "Applying filters");
    
    // Important: Get all order items to filter
    const orderItems = document.querySelectorAll('.order-item');
    
    // Reset display but don't remove filtered-out classes yet
    orderItems.forEach(function(item) {
        // Just reset display to none initially
        item.style.display = 'none';
    });

    // Now apply fresh filters
    let visibleCount = 0;
    
    orderItems.forEach(function(item) {
        const itemStatus = item.dataset.status;
        const itemDate = item.dataset.date;
        
        // Reset filtered state for each item - important to start fresh
        item.classList.remove('filtered-out');
        
        // Determine if this item should be visible based on status filter
        let statusMatch = true;
        if (filterState.statusFilter) {
            if (filterState.statusFilter === 'open') {
                // Open means not completed
                statusMatch = (itemStatus !== 'completed');
                console.log("Order item:", item.dataset.id || 'unknown', "Status:", itemStatus, "Matches open filter:", statusMatch);
            } else if (filterState.statusFilter === 'closed') {
                // Closed means completed
                statusMatch = (itemStatus === 'completed');
            }
            // else 'all' option - keep statusMatch true
        }
        
        // Apply date filters
        let dateMatch = true;
        if (filterState.startDate && itemDate < filterState.startDate) {
            dateMatch = false;
        }
        if (filterState.endDate && itemDate > filterState.endDate) {
            dateMatch = false;
        }
        
        // Only include in visible items if it matches all filters
        if (!statusMatch || !dateMatch) {
            item.classList.add('filtered-out');
        } else {
            visibleCount++;
        }
    });
    
    console.log("Total visible items after filtering:", visibleCount, "Filter applied:", filterState.statusFilter);
    
    // Reset and reinitialize pagination with filtered items
    resetPagination();
}

document.addEventListener('DOMContentLoaded', function() {
    // Lazy loading for images
    initLazyLoading();
    
    // Initialize filters first so pagination will work with filtered items
    initFilters();
    
    // Apply the "open" filter by default (immediately)
    applyDefaultFilter();
    
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
    
    // Use the filterState object instead of querying the DOM again
    // This ensures consistent filter criteria across function calls
    console.log("Showing page", pageNumber, "with filter state:", filterState);
    console.log("DEBUG - visibleItems passed into showFilteredPage:", visibleItems.length);
    
    // Always hide ALL items first (complete reset)
    document.querySelectorAll('.order-item').forEach(item => {
        // Make sure display is set to none
        item.style.display = 'none';
    });
    
    // Verify again that we're only showing items that match the filter criteria
    // Don't assume the filtered-out class is accurate - double verify status match
    for (let i = startIndex; i < endIndex; i++) {
        if (!visibleItems[i]) continue;
        
        const item = visibleItems[i];
        const itemStatus = item.dataset.status;
        
        // Double-check status matches for current filter (safety check)
        let statusMatch = true;
        if (filterState.statusFilter === 'open') {
            statusMatch = (itemStatus !== 'completed');
            console.log("DEBUG showFilteredPage - Item status:", itemStatus, "In OPEN tab, statusMatch:", statusMatch);
        } else if (filterState.statusFilter === 'closed') {
            statusMatch = (itemStatus === 'completed');
            console.log("DEBUG showFilteredPage - Item status:", itemStatus, "In CLOSED tab, statusMatch:", statusMatch);
        } else {
            console.log("DEBUG showFilteredPage - Item status:", itemStatus, "In ALL tab, statusMatch:", statusMatch);
        }
        // else 'all' status - keep statusMatch true
        
        // Log if this item will be displayed
        console.log("DEBUG - Item:", itemStatus, "Will be displayed:", statusMatch && !item.classList.contains('filtered-out'));
        
        // Only show if it matches the filter criteria
        // Important: We need to respect the filtered-out class that's already been set by applyFilters
        if (statusMatch && !item.classList.contains('filtered-out')) {
            item.style.display = 'flex';
        } else {
            // Make sure the item doesn't show if it shouldn't
            item.style.display = 'none';
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
            
            // Skip if this option is already active
            if (activeOption === this) {
                return;
            }
            
            console.log("Switching filter from", activeOption?.dataset.value, "to", value);
            
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
            } catch (e) {
                console.warn('Failed to clear pagination state', e);
            }
            
            // Don't remove any filtered-out classes
            // Instead, let applyFilters set them correctly based on its logic
            document.querySelectorAll('.order-item').forEach(item => {
                // Only reset display property
                item.style.display = 'none';
            });
            
            // Apply filter with a clean slate - this will set correct filtered-out classes
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
    // We already have the filter state from the previous applyFilters call
    // No need to query the DOM again
    console.log("Resetting pagination with filter state:", filterState);
    
    // Important: Double-check which items should be visible based on current filter
    // This is a safety check to ensure our filter state is correct
    const orderItems = document.querySelectorAll('.order-item');
    
    // Verify filter state for all items
    orderItems.forEach(function(item) {
        const itemStatus = item.dataset.status;
        
        // Re-validate status matches for safety
        let shouldBeVisible = true;
        
        if (filterState.statusFilter === 'open') {
            shouldBeVisible = (itemStatus !== 'completed');
            console.log("DEBUG - Item status:", itemStatus, "In OPEN tab, shouldBeVisible:", shouldBeVisible);
        } else if (filterState.statusFilter === 'closed') {
            shouldBeVisible = (itemStatus === 'completed');
            console.log("DEBUG - Item status:", itemStatus, "In CLOSED tab, shouldBeVisible:", shouldBeVisible);
        } else {
            console.log("DEBUG - Item status:", itemStatus, "In ALL tab, shouldBeVisible:", shouldBeVisible);
        }
        // else 'all' option, keep shouldBeVisible true
        
        // Apply date filters too (re-check)
        const itemDate = item.dataset.date;
        
        if (filterState.startDate && itemDate < filterState.startDate) {
            shouldBeVisible = false;
        }
        if (filterState.endDate && itemDate > filterState.endDate) {
            shouldBeVisible = false;
        }
        
        // Ensure correct filtered-out class
        if (!shouldBeVisible) {
            item.classList.add('filtered-out');
            console.log("DEBUG - Adding filtered-out to item:", itemStatus);
        } else {
            item.classList.remove('filtered-out');
            console.log("DEBUG - Removing filtered-out from item:", itemStatus);
        }
    });
    
    // Now get the properly filtered items
    const visibleItems = Array.from(document.querySelectorAll('.order-item:not(.filtered-out)'));
    const itemsPerPage = Number(document.getElementById('itemsPerPage')?.value || 20);
    const totalPages = Math.ceil(visibleItems.length / itemsPerPage);
    
    console.log("Active tab:", filterState.statusFilter, "Visible items:", visibleItems.length);
    
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