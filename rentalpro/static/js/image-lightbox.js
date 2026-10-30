document.addEventListener('DOMContentLoaded', () => {
  const modalElement = document.querySelector('#imageLightbox');
  const fullSizeImage = modalElement?.querySelector('.image-lightbox-content');

  if (!modalElement || !fullSizeImage || !window.bootstrap?.Modal) {
    return;
  }

  const openImage = (image) => {
    fullSizeImage.src = image.currentSrc || image.src;
    fullSizeImage.alt = image.alt;
    window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
  };

  document.querySelectorAll('[data-image-lightbox]').forEach((image) => {
    image.addEventListener('click', () => openImage(image));
    image.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openImage(image);
      }
    });
  });

  modalElement.addEventListener('hidden.bs.modal', () => {
    fullSizeImage.removeAttribute('src');
    fullSizeImage.alt = '';
  });
});
