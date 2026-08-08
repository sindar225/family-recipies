# Tech Task for the AI Code Assistant (Bash Script Update)

```
/
├── index.html (Root navigation)
├── update_index.sh
└── recipes/
    └── pileca-lava/
        ├── pileca-lava.html (The recipe document)
        └── photos/
            ├── image1.jpg
            └── image2.jpg
```
Context: I manage a static recipe website. I am migrating from a flat directory to a nested structure: /recipes/[recipe-slug]/[recipe-slug].html with images in /recipes/[recipe-slug]/photos/*.jpg.

Task: Rewrite my existing update_index.sh script to perform two distinct jobs:

## Job 1: Update the main index.html

1. Find all .html files inside the /recipes/ directory (e.g., find ./recipes -mindepth 2 -name "*.html").
2. Extract the <title> tag from each file.
3. Generate HTML link items (matching my existing recipe-link CSS class) where the href points to the new relative paths.
4. Inject these links into the root ./index.html between the markers <!-- RECIPE_LINKS_START --> and <!-- RECIPE_LINKS_END -->.

## Job 2: Inject the Image Gallery into Recipe HTMLs

1. For every recipe HTML file found, check if its corresponding photos/ directory exists and contains images (.jpg, .png, .jpeg).
2. If photos exist, dynamically generate a JS/CSS gallery modal. The modal must contain:
- A <style> block for the modal (hidden by default, positioned absolute/fixed, z-index: 9999).
- A strict @media print { .gallery-modal, .gallery-btn { display: none !important; } } rule to ensure it does not break A4 printing.
- The HTML for a simple lightbox/slider containing the <img> tags pointing to the local photos.
- Vanilla JavaScript to handle opening the modal, closing it, and navigating between images.
3. Inject a <button class="gallery-btn">📸 Посмотреть фото</button> just inside the <main class="page"> container if it doesn't already exist.
4. Inject the modal HTML/CSS/JS just before the closing </body> tag if it doesn't already exist.
5. Constraint: Use awk for DOM injection to ensure macOS/Linux cross-compatibility. Make sure the script checks for existing injected gallery markers (e.g., <!-- GALLERY_START -->) so it doesn't inject duplicate code if run multiple times.