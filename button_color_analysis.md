.upload-btn {
    background: var(--primary-color);  // Using our variable correctly
}

.details-btn {
    background-color: #0d6efd;  // Direct blue color - PROBLEM
}

.status-update-btn {
    background: var(--bs-primary);  // Using Bootstrap variable - PROBLEM
}
```

2. Variable Definitions:
```css
:root {
    --primary-color: #333333;    // Our correct gray
    --primary-dark: #1a1a1a;     // Our hover state
}
```

3. Issues Found:
- Some buttons use direct color values instead of variables
- Others use Bootstrap's --bs-primary variable
- Inconsistent use of background vs background-color
- Multiple button classes not following the same pattern

## Solution Steps

1. Standardize ALL button classes to use our variables:
```css
/* Base button styles */
.upload-btn,
.details-btn,
.status-update-btn,
.btn-primary {
    background-color: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
}

/* Hover states */
.upload-btn:hover,
.details-btn:hover,
.status-update-btn:hover,
.btn-primary:hover {
    background-color: var(--primary-dark);
    border-color: var(--primary-dark);
    color: white;
}