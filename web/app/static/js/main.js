const fileInput = document.querySelector("[data-file-input]");
const fileName = document.querySelector("[data-file-name]");

if (fileInput && fileName) {
  fileInput.addEventListener("change", () => {
    const selectedFile = fileInput.files && fileInput.files[0];
    fileName.textContent = selectedFile ? selectedFile.name : "";
  });
}

const uploadForm = document.querySelector("[data-upload-form]");

if (uploadForm) {
  const uploadFileInput = uploadForm.querySelector("[data-file-input]");
  const continueButton = uploadForm.querySelector("[data-open-type-modal]");
  const uploadHint = uploadForm.querySelector("[data-upload-hint]");
  const dropzone = uploadForm.querySelector("[data-file-dropzone]");
  const selectedFilePanel = uploadForm.querySelector("[data-file-selection]");
  const selectedFileMeta = uploadForm.querySelector("[data-file-meta]");
  const clearFileButton = uploadForm.querySelector("[data-clear-file]");
  const uploadStepStatus = uploadForm.querySelector("[data-upload-step-status]");
  const typeModal = uploadForm.querySelector("[data-type-modal]");
  const modalFileLabel = typeModal ? typeModal.querySelector("[data-type-modal-file]") : null;
  const closeControls = typeModal ? typeModal.querySelectorAll("[data-type-modal-close]") : [];
  const firstOption = typeModal ? typeModal.querySelector(".type-option") : null;
  let lastFocused = null;

  const hasFile = () => Boolean(uploadFileInput && uploadFileInput.files && uploadFileInput.files.length);

  const formatFileSize = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return "Tamano no disponible";
    }

    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const size = bytes / (1024 ** index);

    return `${size.toLocaleString("es-EC", { maximumFractionDigits: index === 0 ? 0 : 1 })} ${units[index]}`;
  };

  const updateSelectedFile = () => {
    const selectedFile = hasFile() ? uploadFileInput.files[0] : null;

    if (continueButton) {
      continueButton.disabled = !selectedFile;
    }

    if (selectedFilePanel) {
      selectedFilePanel.hidden = !selectedFile;
    }

    if (dropzone) {
      dropzone.classList.toggle("is-selected", Boolean(selectedFile));
    }

    if (selectedFileMeta && selectedFile) {
      const extension = selectedFile.name.includes(".")
        ? selectedFile.name.split(".").pop().toUpperCase()
        : "Archivo";
      selectedFileMeta.textContent = `${extension} - ${formatFileSize(selectedFile.size)}`;
    } else if (selectedFileMeta) {
      selectedFileMeta.textContent = "";
    }

    if (uploadStepStatus) {
      uploadStepStatus.textContent = selectedFile ? "Archivo listo" : "Sin archivo";
      uploadStepStatus.classList.toggle("is-ready", Boolean(selectedFile));
    }

    if (uploadHint) {
      uploadHint.hidden = Boolean(selectedFile);
    }
  };

  const clearSelectedFile = () => {
    if (!uploadFileInput) {
      return;
    }

    uploadFileInput.value = "";
    if (fileName) {
      fileName.textContent = "";
    }
    updateSelectedFile();
  };

  const setDroppedFile = (file) => {
    if (!uploadFileInput || !file) {
      return;
    }

    const transfer = new DataTransfer();
    transfer.items.add(file);
    uploadFileInput.files = transfer.files;
    if (fileName) {
      fileName.textContent = file.name;
    }
    updateSelectedFile();
  };

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
      updateSelectedFile();
    });
  }

  if (clearFileButton) {
    clearFileButton.addEventListener("click", clearSelectedFile);
  }

  if (dropzone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.add("is-dragging");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-dragging");
      });
    });

    dropzone.addEventListener("drop", (event) => {
      const droppedFile = event.dataTransfer && event.dataTransfer.files
        ? event.dataTransfer.files[0]
        : null;
      setDroppedFile(droppedFile);
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

  updateSelectedFile();

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
