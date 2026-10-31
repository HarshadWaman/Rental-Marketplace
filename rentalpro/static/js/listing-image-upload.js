document.addEventListener('DOMContentLoaded', () => {
  const imageInput = document.querySelector('#id_images');
  const filename = document.querySelector('[data-image-filename]');

  if (!imageInput || !filename) {
    return;
  }

  document.querySelectorAll('[data-image-source]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.imageSource === 'camera') {
        imageInput.setAttribute('capture', 'environment');
      } else {
        imageInput.removeAttribute('capture');
      }
      imageInput.click();
    });
  });

  imageInput.addEventListener('change', () => {
    filename.textContent = imageInput.files.length
      ? `Selected: ${Array.from(imageInput.files, (file) => file.name).join(', ')}`
      : '';
  });
});
