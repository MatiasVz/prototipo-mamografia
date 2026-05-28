const fileInput = document.querySelector("[data-file-input]");
const fileName = document.querySelector("[data-file-name]");

if (fileInput && fileName) {
  const defaultMessage = fileName.textContent;

  fileInput.addEventListener("change", () => {
    const selectedFile = fileInput.files && fileInput.files[0];
    fileName.textContent = selectedFile ? `Archivo seleccionado: ${selectedFile.name}` : defaultMessage;
  });
}

const uploadForm = document.querySelector("[data-upload-form]");

if (uploadForm) {
  const uploadFileInput = uploadForm.querySelector("[data-file-input]");
  const continueButton = uploadForm.querySelector("[data-open-type-modal]");
  const uploadHint = uploadForm.querySelector("[data-upload-hint]");
  const typeModal = uploadForm.querySelector("[data-type-modal]");
  const modalFileLabel = typeModal ? typeModal.querySelector("[data-type-modal-file]") : null;
  const closeControls = typeModal ? typeModal.querySelectorAll("[data-type-modal-close]") : [];
  const firstOption = typeModal ? typeModal.querySelector(".type-option") : null;
  let lastFocused = null;

  const hasFile = () => Boolean(uploadFileInput && uploadFileInput.files && uploadFileInput.files.length);

  const openModal = () => {
    if (!typeModal || !hasFile()) {
      return;
    }

    if (modalFileLabel) {
      modalFileLabel.textContent = `Archivo seleccionado: ${uploadFileInput.files[0].name}`;
    }

    lastFocused = document.activeElement;
    typeModal.hidden = false;
    typeModal.classList.add("is-open");
    document.body.classList.add("modal-open");

    if (firstOption) {
      firstOption.focus();
    }
  };

  const closeModal = () => {
    if (!typeModal) {
      return;
    }

    typeModal.hidden = true;
    typeModal.classList.remove("is-open");
    document.body.classList.remove("modal-open");

    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  };

  if (uploadFileInput) {
    uploadFileInput.addEventListener("change", () => {
      if (continueButton) {
        continueButton.disabled = !hasFile();
      }

      if (uploadHint) {
        uploadHint.hidden = true;
      }

      if (hasFile()) {
        openModal();
      }
    });
  }

  if (continueButton) {
    continueButton.addEventListener("click", () => {
      if (hasFile()) {
        openModal();
      } else if (uploadHint) {
        uploadHint.hidden = false;
      }
    });
  }

  closeControls.forEach((control) => {
    control.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && typeModal && typeModal.classList.contains("is-open")) {
      closeModal();
    }
  });
}

const roiCropTool = document.querySelector("[data-roi-crop-tool]");

if (roiCropTool) {
  const canvas = roiCropTool.querySelector("[data-roi-crop-canvas]");
  const statusText = roiCropTool.querySelector("[data-roi-crop-status]");
  const submitButton = roiCropTool.querySelector("[data-roi-crop-submit]");
  const inputX = roiCropTool.querySelector("[data-roi-crop-x]");
  const inputY = roiCropTool.querySelector("[data-roi-crop-y]");
  const inputWidth = roiCropTool.querySelector("[data-roi-crop-width]");
  const inputHeight = roiCropTool.querySelector("[data-roi-crop-height]");
  const context = canvas.getContext("2d");
  const image = new Image();
  let displayWidth = 0;
  let displayHeight = 0;
  let isSelecting = false;
  let startPoint = null;
  let selection = null;

  image.addEventListener("load", () => {
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
  });

  image.src = roiCropTool.dataset.imageSrc;

  canvas.addEventListener("pointerdown", (event) => {
    if (!displayWidth || !displayHeight) {
      return;
    }

    isSelecting = true;
    startPoint = getCanvasPoint(event);
    selection = null;
    clearSelectionInputs();
    canvas.setPointerCapture(event.pointerId);
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!isSelecting || !startPoint) {
      return;
    }

    const currentPoint = getCanvasPoint(event);
    selection = normalizeSelection(startPoint, currentPoint);
    drawCanvas();
  });

  canvas.addEventListener("pointerup", (event) => {
    if (!isSelecting) {
      return;
    }

    isSelecting = false;
    canvas.releasePointerCapture(event.pointerId);
    updateSelectionInputs();
  });

  function resizeCanvas() {
    const containerWidth = Math.max(roiCropTool.clientWidth, 1);
    const maxCanvasWidth = Math.min(image.naturalWidth, containerWidth);
    const scale = maxCanvasWidth / image.naturalWidth;

    displayWidth = Math.round(image.naturalWidth * scale);
    displayHeight = Math.round(image.naturalHeight * scale);
    canvas.width = displayWidth;
    canvas.height = displayHeight;
    drawCanvas();
  }

  function drawCanvas() {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, displayWidth, displayHeight);

    if (!selection) {
      return;
    }

    context.fillStyle = "rgba(18, 100, 163, 0.18)";
    context.strokeStyle = "#ffffff";
    context.lineWidth = 2;
    context.fillRect(selection.x, selection.y, selection.width, selection.height);
    context.strokeRect(selection.x, selection.y, selection.width, selection.height);
  }

  function getCanvasPoint(event) {
    const bounds = canvas.getBoundingClientRect();

    return {
      x: clamp(event.clientX - bounds.left, 0, displayWidth),
      y: clamp(event.clientY - bounds.top, 0, displayHeight),
    };
  }

  function normalizeSelection(start, end) {
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    const width = Math.abs(end.x - start.x);
    const height = Math.abs(end.y - start.y);

    return { x, y, width, height };
  }

  function updateSelectionInputs() {
    if (!selection || selection.width < 4 || selection.height < 4) {
      clearSelectionInputs();
      statusText.textContent = "Seleccion pendiente.";
      return;
    }

    const scaleX = image.naturalWidth / displayWidth;
    const scaleY = image.naturalHeight / displayHeight;
    const cropX = Math.round(selection.x * scaleX);
    const cropY = Math.round(selection.y * scaleY);
    const cropWidth = Math.round(selection.width * scaleX);
    const cropHeight = Math.round(selection.height * scaleY);

    inputX.value = cropX;
    inputY.value = cropY;
    inputWidth.value = cropWidth;
    inputHeight.value = cropHeight;
    submitButton.disabled = false;
    statusText.textContent = `ROI seleccionada: ${cropWidth} x ${cropHeight} px.`;
  }

  function clearSelectionInputs() {
    inputX.value = "";
    inputY.value = "";
    inputWidth.value = "";
    inputHeight.value = "";
    submitButton.disabled = true;
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(value, maximum));
  }
}
