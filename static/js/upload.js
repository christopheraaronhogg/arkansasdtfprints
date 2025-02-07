document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const preview = document.getElementById('image-preview');
    const progressBar = document.getElementById('upload-progress');
    const dimensionsInfo = document.getElementById('dimensions-info');
    const costInfo = document.getElementById('cost-info');
    
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Show preview
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
                preview.style.display = 'block';
                
                // Create temporary image to get dimensions
                const img = new Image();
                img.onload = function() {
                    const widthInches = (this.width / 300).toFixed(2);
                    const heightInches = (this.height / 300).toFixed(2);
                    dimensionsInfo.textContent = `Dimensions: ${widthInches}" × ${heightInches}"`;
                    const area = widthInches * heightInches;
                    const cost = (5 + (area * 0.15)).toFixed(2);
                    costInfo.textContent = `Estimated Cost: $${cost}`;
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }
    });
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        
        // Reset progress bar
        progressBar.style.width = '0%';
        progressBar.parentElement.style.display = 'block';
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Show success message
            showAlert('Order successfully submitted! Check your email for confirmation.', 'success');
            form.reset();
            preview.style.display = 'none';
            dimensionsInfo.textContent = '';
            costInfo.textContent = '';
            progressBar.parentElement.style.display = 'none';
        })
        .catch(error => {
            showAlert(error.message, 'danger');
            progressBar.parentElement.style.display = 'none';
        });
    });
    
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        form.insertAdjacentElement('beforebegin', alertDiv);
    }
});
