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

    // Initialize with the first image
    imageElement.src = imageUrls[currentIndex];

    // Event listeners for navigation buttons
    nextButton.addEventListener('click', () => {
        currentIndex = (currentIndex + 1) % imageUrls.length;
        imageElement.src = imageUrls[currentIndex];
    });

    prevButton.addEventListener('click', () => {
        currentIndex = (currentIndex - 1 + imageUrls.length) % imageUrls.length;
        imageElement.src = imageUrls[currentIndex];
    });
});
