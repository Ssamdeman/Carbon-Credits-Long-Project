document.addEventListener('DOMContentLoaded', () => {
    const imageElement = document.getElementById('satellite-image');
    const prevButton = document.getElementById('prev-button');
    const nextButton = document.getElementById('next-button');

    // Retrieve image URLs from data attributes
    const satelliteImageUrl = imageElement.getAttribute('data-satellite-url');
    const landcoverImageUrl = imageElement.getAttribute('data-landcover-url');

    // Array of image URLs
    const imageUrls = [satelliteImageUrl, landcoverImageUrl];
    let currentIndex = 0;

    // Create loading icon
    const loadingIcon = document.createElement('div');
    loadingIcon.className = 'loading-icon';
    imageElement.parentNode.insertBefore(loadingIcon, imageElement);

    // Function to handle image loading
    const loadImage = (url) => {
        loadingIcon.style.display = 'block';
        const img = new Image();
        img.src = url;
        img.onload = () => {
            imageElement.src = url;
            loadingIcon.style.display = 'none';
        };
    };

    // Initialize with the first image
    loadImage(imageUrls[currentIndex]);

    // Event listeners for navigation buttons
    nextButton.addEventListener('click', () => {
        currentIndex = (currentIndex + 1) % imageUrls.length;
        loadImage(imageUrls[currentIndex]);
    });

    prevButton.addEventListener('click', () => {
        currentIndex = (currentIndex - 1 + imageUrls.length) % imageUrls.length;
        loadImage(imageUrls[currentIndex]);
    });
});