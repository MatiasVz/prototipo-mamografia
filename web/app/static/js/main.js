const fileInput = document.querySelector("[data-file-input]");
const fileName = document.querySelector("[data-file-name]");

if (fileInput && fileName) {
  const defaultMessage = fileName.textContent;

  fileInput.addEventListener("change", () => {
    const selectedFile = fileInput.files && fileInput.files[0];
    fileName.textContent = selectedFile ? `Archivo seleccionado: ${selectedFile.name}` : defaultMessage;
  });
}
