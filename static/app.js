const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];

// Preserve the photo slot and its caption when a stored or remote image is missing.
const photoImageSelector = '.submission-photo img,.photo-manager-card>img,.animal-photo img,.gallery-main img,.gallery-thumb img,.gallery-lightbox img,.summary-card>img';
const showUnavailablePhoto = (photo) => {
  if (!(photo instanceof HTMLImageElement) || !photo.matches(photoImageSelector)) return;
  if (photo.nextElementSibling?.classList.contains('photo-unavailable')) return;
  const placeholder = document.createElement('span');
  placeholder.className = 'photo-unavailable';
  placeholder.setAttribute('role', 'img');
  placeholder.setAttribute('aria-label', `Photo unavailable. ${photo.alt || ''}`.trim());
  const icon = document.createElement('span');
  icon.className = 'photo-unavailable-icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = '▧';
  const label = document.createElement('span');
  label.textContent = 'Photo unavailable';
  placeholder.append(icon, label);
  photo.hidden = true;
  photo.after(placeholder);
};
document.addEventListener('error', (event) => showUnavailablePhoto(event.target), true);
document.addEventListener('load', (event) => {
  const photo = event.target;
  if (photo instanceof HTMLImageElement && photo.matches(photoImageSelector) && photo.naturalWidth) {
    if (photo.nextElementSibling?.classList.contains('photo-unavailable')) {
      photo.nextElementSibling.remove();
      photo.hidden = false;
    }
  }
}, true);
$$(photoImageSelector).forEach((photo) => {
  if (photo.complete && !photo.naturalWidth) showUnavailablePhoto(photo);
});

$$('[data-dialog-open]').forEach((button) => button.addEventListener('click', () => {
  document.getElementById(button.dataset.dialogOpen)?.showModal();
}));
$$('[data-dialog-close]').forEach((button) => button.addEventListener('click', () => {
  button.closest('dialog')?.close();
}));

const gallery = $('[data-gallery]');
if (gallery) {
  const main = $('[data-gallery-main]', gallery);
  const opener = $('[data-gallery-open]', gallery);
  const thumbs = $$('.gallery-thumb', gallery);
  const dialog = $('[data-gallery-dialog]');
  const position = $('[data-gallery-position]', gallery);
  const items = thumbs.length
    ? thumbs.map((thumb) => ({src: thumb.dataset.gallerySrc, alt: thumb.dataset.galleryAlt}))
    : main ? [{src: main.src, alt: main.alt}] : [];
  let index = 0;

  const select = (requestedIndex) => {
    if (!items.length) return;
    index = (requestedIndex + items.length) % items.length;
    if (main) {
      main.src = items[index].src;
      main.alt = items[index].alt;
    }
    if (position) position.textContent = String(index + 1);
    thumbs.forEach((thumb, thumbIndex) => thumb.classList.toggle('active', thumbIndex === index));
    const lightboxImage = dialog ? $('[data-gallery-lightbox]', dialog) : null;
    if (lightboxImage) {
      lightboxImage.src = items[index].src;
      lightboxImage.alt = items[index].alt;
    }
  };

  thumbs.forEach((thumb, thumbIndex) => thumb.addEventListener('click', () => select(thumbIndex)));
  $('[data-gallery-inline-prev]', gallery)?.addEventListener('click', () => select(index - 1));
  $('[data-gallery-inline-next]', gallery)?.addEventListener('click', () => select(index + 1));
  opener?.addEventListener('click', () => {
    if (!dialog) return;
    select(index);
    dialog.showModal();
    document.documentElement.classList.add('lightbox-open');
  });
  if (dialog) {
    $('[data-gallery-close]', dialog)?.addEventListener('click', () => dialog.close());
    $('[data-gallery-prev]', dialog)?.addEventListener('click', () => select(index - 1));
    $('[data-gallery-next]', dialog)?.addEventListener('click', () => select(index + 1));
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => document.documentElement.classList.remove('lightbox-open'));
    document.addEventListener('keydown', (event) => {
      if (!dialog.open) return;
      if (event.key === 'ArrowLeft') select(index - 1);
      if (event.key === 'ArrowRight') select(index + 1);
    });
  }
}

const initializePhotoEditor = (photoEditor) => {
  if (!photoEditor || photoEditor.dataset.uploadInitialized === 'true') return;
  photoEditor.dataset.uploadInitialized = 'true';
  const newCover = $('[name="make_new_primary"]', photoEditor);
  const coverChoices = $$('[name="primary_photo"]', photoEditor);
  const removeChoices = $$('[name="remove_photo"]', photoEditor);
  const photoInput = $('[name="photos"]', photoEditor);
  const selectionMessage = $('[data-file-selection-message]', photoEditor);

  const formatBytes = (bytes) => {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KiB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
  };
  const updateSelectionMessage = () => {
    if (!photoInput || !selectionMessage || photoInput.disabled) return;
    const files = [...photoInput.files];
    if (!files.length) {
      selectionMessage.textContent = 'No new photos selected.';
      return;
    }
    const totalBytes = files.reduce((total, file) => total + file.size, 0);
    const noun = files.length === 1 ? 'photo' : 'photos';
    const maximum = Number(photoEditor.dataset.maxFiles || 0);
    selectionMessage.textContent = maximum && files.length > maximum
      ? `${files.length} ${noun} selected, but no more than ${maximum} are allowed. Submit to see the full validation message.`
      : `${files.length} ${noun} selected (${formatBytes(totalBytes)} total). Upload progress will begin when you save.`;
  };
  photoInput?.addEventListener('change', updateSelectionMessage);

  newCover?.addEventListener('change', () => {
    if (newCover.checked) coverChoices.forEach((choice) => { choice.checked = false; });
  });
  coverChoices.forEach((choice) => choice.addEventListener('change', () => {
    if (!choice.checked) return;
    if (newCover) newCover.checked = false;
    const removal = $(`[name="remove_photo"][value="${choice.value}"]`, photoEditor);
    if (removal) removal.checked = false;
  }));
  removeChoices.forEach((choice) => choice.addEventListener('change', () => {
    if (!choice.checked) return;
    const cover = $(`[name="primary_photo"][value="${choice.value}"]`, photoEditor);
    if (cover) cover.checked = false;
  }));

  photoEditor.addEventListener('submit', (event) => {
    if (!photoInput || photoInput.disabled || !photoInput.files.length) return;

    event.preventDefault();
    const uploadStatus = $('[data-upload-status]', photoEditor);
    const progress = $('[data-upload-progress]', photoEditor);
    const message = $('[data-upload-message]', photoEditor);
    const uploadLabel = $('[data-upload-label]', photoEditor);
    const submitButtons = $$('button[type="submit"], button:not([type]), input[type="submit"]', photoEditor);
    const fileCount = photoInput.files.length;
    const fileNoun = fileCount === 1 ? 'photo' : 'photos';
    const formData = new FormData(photoEditor);
    const request = new XMLHttpRequest();

    uploadStatus.hidden = false;
    progress.value = 0;
    uploadLabel.textContent = `Overall upload progress for ${fileCount} ${fileNoun}`;
    message.textContent = `Overall upload started: 0% of ${fileCount} ${fileNoun}.`;
    submitButtons.forEach((button) => { button.disabled = true; });

    request.open(photoEditor.method || 'POST', photoEditor.action || window.location.href);
    request.upload.addEventListener('progress', (uploadEvent) => {
      if (!uploadEvent.lengthComputable) {
        message.textContent = `Overall upload in progress for ${fileCount} ${fileNoun}…`;
        return;
      }
      const percent = Math.round((uploadEvent.loaded / uploadEvent.total) * 100);
      progress.value = percent;
      progress.textContent = `${percent}%`;
      message.textContent = percent < 100
        ? `Overall upload: ${percent}% of ${fileCount} ${fileNoun}.`
        : `All ${fileCount} ${fileNoun} uploaded. Processing images…`;
    });
    request.addEventListener('load', () => {
      if (request.status < 200 || request.status >= 400) {
        message.textContent = `Upload failed with status ${request.status}. Please try again.`;
        submitButtons.forEach((button) => { button.disabled = false; });
        return;
      }
      const responseUrl = new URL(request.responseURL || window.location.href);
      if (responseUrl.pathname !== window.location.pathname) {
        window.location.assign(responseUrl.href);
        return;
      }
      const parsed = new DOMParser().parseFromString(request.responseText, 'text/html');
      document.title = parsed.title;
      document.body.replaceWith(parsed.body);
      initializePhotoEditors();
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
    request.addEventListener('error', () => {
      message.textContent = 'The upload could not be completed. Check your connection and try again.';
      submitButtons.forEach((button) => { button.disabled = false; });
    });
    request.send(formData);
  });
};

const initializePhotoEditors = () => $$('[data-photo-editor]').forEach(initializePhotoEditor);
initializePhotoEditors();

const createSelectionCropper = ({stage, image, selection, cropInput, ratio, maxWidth = 900, maxHeight = 680}) => {
  let stageWidth = 0;
  let stageHeight = 0;
  let currentRatio = Number(ratio) || 1;
  let crop = {x: 0, y: 0, width: 0, height: 0};
  let ready = false;

  const savedCrop = () => {
    try { return JSON.parse(cropInput?.value || '{}'); } catch (_) { return {}; }
  };
  const minimumSize = () => {
    const maximumWidth = Math.min(stageWidth, stageHeight * currentRatio);
    const shortSide = Math.min(Math.min(stageWidth, stageHeight) * 0.12, maximumWidth / Math.max(1, currentRatio));
    return currentRatio >= 1
      ? {width: shortSide * currentRatio, height: shortSide}
      : {width: shortSide, height: shortSide / currentRatio};
  };
  const constrain = (candidate) => {
    const minimum = minimumSize();
    let width = Math.max(minimum.width, Math.min(stageWidth, candidate.width));
    let height = width / currentRatio;
    if (height > stageHeight) {
      height = stageHeight;
      width = height * currentRatio;
    }
    let x = Math.max(0, Math.min(stageWidth - width, candidate.x));
    let y = Math.max(0, Math.min(stageHeight - height, candidate.y));
    return {x, y, width, height};
  };
  const write = () => {
    if (!ready) return;
    crop = constrain(crop);
    Object.assign(selection.style, {
      left: `${crop.x}px`, top: `${crop.y}px`, width: `${crop.width}px`, height: `${crop.height}px`,
    });
    cropInput.value = JSON.stringify({
      x: crop.x / stageWidth,
      y: crop.y / stageHeight,
      width: crop.width / stageWidth,
      height: crop.height / stageHeight,
    });
    cropInput.dispatchEvent(new Event('cropchange', {bubbles: true}));
  };
  const centered = (fill = 0.9) => {
    let width = stageWidth * fill;
    let height = width / currentRatio;
    if (height > stageHeight * fill) {
      height = stageHeight * fill;
      width = height * currentRatio;
    }
    crop = {x: (stageWidth - width) / 2, y: (stageHeight - height) / 2, width, height};
  };
  const fromNormalized = (value) => {
    const requested = {
      x: Number(value.x || 0) * stageWidth,
      y: Number(value.y || 0) * stageHeight,
      width: Number(value.width || 0) * stageWidth,
      height: Number(value.height || 0) * stageHeight,
    };
    if (!(requested.width > 0 && requested.height > 0)) {
      centered();
      return;
    }
    const centerX = requested.x + requested.width / 2;
    const centerY = requested.y + requested.height / 2;
    let width = requested.width;
    let height = width / currentRatio;
    if (height > requested.height) {
      height = requested.height;
      width = height * currentRatio;
    }
    crop = constrain({x: centerX - width / 2, y: centerY - height / 2, width, height});
  };
  const layout = (useStoredCrop = true) => {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const retained = ready ? savedCrop() : null;
    const shellWidth = Math.max(1, stage.parentElement.clientWidth);
    const availableWidth = Math.min(maxWidth, shellWidth);
    const availableHeight = Math.min(maxHeight, Math.max(320, window.innerHeight * 0.68));
    const scale = Math.min(availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
    stageWidth = Math.max(1, image.naturalWidth * scale);
    stageHeight = Math.max(1, image.naturalHeight * scale);
    stage.style.width = `${stageWidth}px`;
    stage.style.height = `${stageHeight}px`;
    // Both dimensions and the crop coordinates use the same uniform scale.
    // A CSS width cap or flex shrink must never change just one dimension.
    stage.style.maxWidth = 'none';
    stage.style.flex = '0 0 auto';
    image.style.width = '100%';
    image.style.height = '100%';
    image.hidden = false;
    selection.hidden = false;
    ready = true;
    if (useStoredCrop) fromNormalized(retained || savedCrop());
    else centered();
    write();
  };
  const setRatio = (nextRatio, reset = true) => {
    currentRatio = Number(nextRatio) || 1;
    if (!ready) return;
    if (reset) centered();
    else fromNormalized(savedCrop());
    write();
  };
  const stagePoint = (event) => {
    const bounds = stage.getBoundingClientRect();
    return {x: event.clientX - bounds.left, y: event.clientY - bounds.top};
  };
  const beginMove = (event) => {
    if (!ready || event.target.closest('[data-crop-handle]')) return;
    event.preventDefault();
    selection.setPointerCapture(event.pointerId);
    const start = stagePoint(event);
    const original = {...crop};
    const move = (nextEvent) => {
      const point = stagePoint(nextEvent);
      crop = constrain({...original, x: original.x + point.x - start.x, y: original.y + point.y - start.y});
      write();
    };
    const end = () => {
      selection.removeEventListener('pointermove', move);
      selection.removeEventListener('pointerup', end);
      selection.removeEventListener('pointercancel', end);
    };
    selection.addEventListener('pointermove', move);
    selection.addEventListener('pointerup', end);
    selection.addEventListener('pointercancel', end);
  };
  const beginResize = (event) => {
    if (!ready) return;
    event.preventDefault();
    event.stopPropagation();
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const corner = handle.dataset.cropHandle;
    const right = corner.includes('e');
    const bottom = corner.includes('s');
    const anchorX = right ? crop.x : crop.x + crop.width;
    const anchorY = bottom ? crop.y : crop.y + crop.height;
    const resize = (nextEvent) => {
      const point = stagePoint(nextEvent);
      const maximumWidth = right ? stageWidth - anchorX : anchorX;
      const maximumHeight = bottom ? stageHeight - anchorY : anchorY;
      const minimum = minimumSize();
      const requestedWidth = Math.max(Math.abs(point.x - anchorX), Math.abs(point.y - anchorY) * currentRatio);
      const width = Math.max(minimum.width, Math.min(requestedWidth, maximumWidth, maximumHeight * currentRatio));
      const height = Math.max(minimum.height, width / currentRatio);
      crop = constrain({
        x: right ? anchorX : anchorX - width,
        y: bottom ? anchorY : anchorY - height,
        width,
        height,
      });
      write();
    };
    const end = () => {
      handle.removeEventListener('pointermove', resize);
      handle.removeEventListener('pointerup', end);
      handle.removeEventListener('pointercancel', end);
    };
    handle.addEventListener('pointermove', resize);
    handle.addEventListener('pointerup', end);
    handle.addEventListener('pointercancel', end);
  };
  const resizeFromCenter = (factor) => {
    const centerX = crop.x + crop.width / 2;
    const centerY = crop.y + crop.height / 2;
    const width = crop.width * factor;
    crop = constrain({x: centerX - width / 2, y: centerY - width / currentRatio / 2, width, height: width / currentRatio});
    write();
  };

  selection.addEventListener('pointerdown', beginMove);
  $$('[data-crop-handle]', selection).forEach((handle) => handle.addEventListener('pointerdown', beginResize));
  selection.addEventListener('keydown', (event) => {
    const amount = event.shiftKey ? 20 : 5;
    if (event.key === 'ArrowLeft') crop.x -= amount;
    else if (event.key === 'ArrowRight') crop.x += amount;
    else if (event.key === 'ArrowUp') crop.y -= amount;
    else if (event.key === 'ArrowDown') crop.y += amount;
    else if (event.key === '+' || event.key === '=') return event.preventDefault(), resizeFromCenter(1.05);
    else if (event.key === '-' || event.key === '_') return event.preventDefault(), resizeFromCenter(0.95);
    else return;
    event.preventDefault();
    write();
  });
  window.addEventListener('resize', () => layout(true));
  return {layout, setRatio};
};

const brandingForm = $('[data-branding-form]');
if (brandingForm) {
  const csrfToken = $('[name="csrfmiddlewaretoken"]', brandingForm)?.value;
  const previewTemplate = brandingForm.dataset.previewUrlTemplate;
  let imageSession = null;
  let startingSession = false;
  let previewCount = 0;
  const startImageSession = async () => {
    if (imageSession || startingSession) return;
    startingSession = true;
    try {
      const data = new FormData(); data.append('action', 'start');
      const response = await fetch(previewTemplate.replace('ASSET_KIND', 'logo'), {method:'POST', headers:{'X-CSRFToken':csrfToken}, body:data});
      if (!response.ok) throw new Error('Could not start image editing session.');
      const result = await response.json();
      imageSession = performance.now() + result.remaining_seconds * 1000;
      $('[data-branding-session]', brandingForm).hidden = false;
      const tick = () => {
        const seconds = Math.max(0, Math.ceil((imageSession - performance.now()) / 1000));
        $('[data-branding-countdown]', brandingForm).textContent = seconds ? `Image editing time remaining: ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : 'Image editing expired. Discard changes and select your images again.';
        if (seconds) setTimeout(tick, 250);
      }; tick();
    } finally { startingSession = false; }
  };
  $('[data-branding-discard]', brandingForm)?.addEventListener('click', async () => {
    const data = new FormData(); data.append('action', 'discard');
    await fetch(previewTemplate.replace('ASSET_KIND', 'logo'), {method:'POST', headers:{'X-CSRFToken':csrfToken}, body:data});
    window.location.reload();
  });
  brandingForm.addEventListener('submit', (event) => {
    if (previewCount || startingSession || (imageSession && performance.now() >= imageSession)) {
      event.preventDefault();
      alert(previewCount ? 'Wait for image uploads to finish.' : 'Image editing expired. Discard changes and select your images again.');
      return;
    }
    const hasFiles = $$('input[type=file]', brandingForm).some((input) => input.files.length);
    if (!hasFiles) return;
    event.preventDefault();
    const message = document.createElement('p'); message.setAttribute('role', 'status'); message.textContent = 'Uploading settings…'; brandingForm.append(message);
    const request = new XMLHttpRequest(); request.open('POST', brandingForm.action || location.href);
    request.upload.onprogress = (progress) => { message.textContent = progress.lengthComputable ? `Saving image uploads: ${Math.round(progress.loaded / progress.total * 100)}%` : 'Saving image uploads…'; };
    request.upload.onload = () => { message.textContent = 'Uploads complete. Saving images and settings…'; };
    request.onload = () => { document.open(); document.write(request.responseText); document.close(); };
    request.onerror = () => { message.textContent = 'Save failed. Check your connection and try again.'; };
    request.send(new FormData(brandingForm));
  });

  $$('[data-live-name]', brandingForm).forEach((node) => {
    $('[name="name"]', brandingForm)?.addEventListener('input', (event) => { node.textContent = event.target.value; });
  });
  $$('[data-color-picker]', brandingForm).forEach((picker) => {
    const textInput = document.getElementById(picker.dataset.colorTarget);
    const variable = textInput?.name === 'primary_color' ? '--primary' : '--secondary';
    const apply = (value) => {
      if (!/^#[0-9a-f]{6}$/i.test(value)) return;
      picker.value = value;
      document.documentElement.style.setProperty(variable, value);
    };
    picker.addEventListener('input', () => { if (textInput) textInput.value = picker.value.toUpperCase(); apply(picker.value); });
    textInput?.addEventListener('input', () => apply(textInput.value));
  });

  $$('[data-branding-cropper]', brandingForm).forEach((cropper) => {
    const kind = cropper.dataset.kind;
    const stage = $('[data-crop-stage]', cropper);
    const image = $('[data-crop-image]', cropper);
    const selection = $('[data-crop-selection]', cropper);
    const placeholder = $('[data-crop-placeholder]', cropper);
    const status = $('[data-crop-status]', cropper);
    const fileInput = $(`[name="${kind}_upload"]`, cropper);
    const cropInput = $(`[name="${kind}_crop"]`, cropper);
    let objectUrl = null;
    let initializing = true;
    const controller = createSelectionCropper({
      stage,
      image,
      selection,
      cropInput,
      ratio: Number(cropper.dataset.ratio || 1),
      maxWidth: kind === 'banner' ? 900 : 430,
      maxHeight: kind === 'banner' ? 520 : 520,
    });
    const imageReady = (useStoredCrop = false) => {
      image.hidden = false;
      placeholder.hidden = true;
      controller.layout(useStoredCrop);
      initializing = false;
    };
    if (image.src) {
      if (image.complete) imageReady(true);
      else image.addEventListener('load', () => imageReady(true), {once: true});
    } else selection.hidden = true;
    cropInput.addEventListener('cropchange', () => { if (!initializing) startImageSession().catch((error) => { status.textContent = error.message; }); });

    fileInput?.addEventListener('change', async () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      await startImageSession();
      status.textContent = 'Preparing crop preview…';
      previewCount += 1;
      const formData = new FormData();
      formData.append('image', file);
      try {
        const blob = await new Promise((resolve, reject) => {
          const request = new XMLHttpRequest();
          request.open('POST', previewTemplate.replace('ASSET_KIND', kind));
          request.setRequestHeader('X-CSRFToken', csrfToken);
          request.responseType = 'blob';
          request.upload.addEventListener('progress', (event) => {
            status.textContent = event.lengthComputable ? `Uploading image: ${Math.round(event.loaded / event.total * 100)}%` : 'Uploading image…';
          });
          request.upload.addEventListener('load', () => { status.textContent = 'Upload complete. Preparing preview…'; });
          request.onload = () => request.status >= 200 && request.status < 300 ? resolve(request.response) : reject(new Error('The image preview could not be generated. Check the format and size.'));
          request.onerror = () => reject(new Error('Upload failed. Check your connection and try again.'));
          request.send(formData);
        });
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = URL.createObjectURL(blob);
        image.onload = () => {
          imageReady(false);
          status.textContent = 'Move or resize the 3×3 selection. The image remains fixed.';
          if (kind === 'banner') $('[data-live-banner]', brandingForm)?.style.setProperty('background-image', `linear-gradient(#173d32b8,#173d32b8),url("${objectUrl}")`);
          if (kind === 'logo') $('[data-live-logo]', brandingForm)?.setAttribute('src', objectUrl);
          if (kind === 'favicon') $('[data-live-favicon]', brandingForm)?.setAttribute('src', objectUrl);
        };
        image.src = objectUrl;
      } catch (error) {
        status.textContent = error.message;
      } finally { previewCount -= 1; }
    });
  });
}

const photoCropForm = $('[data-photo-crop-form]');
if (photoCropForm) {
  const landscapeRatio = Number(photoCropForm.dataset.landscapeRatio || 4 / 3);
  $$('[data-photo-cropper]', photoCropForm).forEach((cropper) => {
    const stage = $('[data-photo-crop-stage]', cropper);
    const image = $('[data-photo-crop-image]', cropper);
    const selection = $('[data-photo-crop-selection]', cropper);
    const cropValue = $('[data-photo-crop-value]', cropper);
    const orientation = $('[data-photo-orientation]', cropper);
    const controller = createSelectionCropper({stage, image, selection, cropInput: cropValue, ratio: landscapeRatio});
    const applyOrientation = () => {
      const ratio = orientation.value === 'portrait' ? 1 / landscapeRatio : landscapeRatio;
      controller.setRatio(ratio, true);
    };
    const imageLoaded = () => {
      orientation.value = image.naturalHeight > image.naturalWidth ? 'portrait' : 'landscape';
      controller.setRatio(orientation.value === 'portrait' ? 1 / landscapeRatio : landscapeRatio, true);
      controller.layout(false);
    };
    if (image.complete && image.naturalWidth) imageLoaded(); else image.addEventListener('load', imageLoaded, {once: true});
    orientation.addEventListener('change', applyOrientation);
  });

  const countdown = $('[data-batch-countdown]');
  const timeNode = $('[data-countdown-time]', countdown);
  const statusNode = $('[data-countdown-status]', countdown);
  const finalizeButton = $('[data-finalize-crops]', photoCropForm);
  const initialRemaining = Math.max(0, new Date(countdown.dataset.expiresAt) - new Date(countdown.dataset.serverNow));
  const started = performance.now();
  let announced = new Set();
  const updateCountdown = () => {
    const remaining = Math.max(0, initialRemaining - (performance.now() - started));
    const totalSeconds = Math.ceil(remaining / 1000);
    const minutes = Math.floor(totalSeconds / 60), seconds = totalSeconds % 60;
    timeNode.textContent = `${minutes}:${String(seconds).padStart(2, '0')}`;
    for (const threshold of [600, 300, 60]) {
      if (totalSeconds <= threshold && !announced.has(threshold)) {
        announced.add(threshold); statusNode.textContent = `${Math.ceil(threshold / 60)} minute${threshold === 60 ? '' : 's'} remaining.`;
      }
    }
    if (remaining <= 0) {
      statusNode.textContent = 'This crop session has expired.';
      finalizeButton.disabled = true;
      $$('input,select', photoCropForm).forEach((control) => { control.disabled = true; });
      return;
    }
    window.setTimeout(updateCountdown, 250);
  };
  updateCountdown();
}

const systemRefreshForm = $('[data-system-refresh-form]');
if (systemRefreshForm) {
  const select = $('[data-system-refresh]', systemRefreshForm);
  const status = $('[data-system-refresh-status]', systemRefreshForm);
  const snapshot = $('[data-system-snapshot]');
  let source;

  const closeSystemStream = () => {
    source?.close();
    source = null;
  };
  const startSystemStream = () => {
    closeSystemStream();
    if (document.hidden) return;
    const seconds = Number(select?.value || 5);
    const streamUrl = new URL(systemRefreshForm.dataset.systemStreamUrl, window.location.href);
    streamUrl.searchParams.set('refresh', String(seconds));
    if (status) status.textContent = 'Connecting for live updates…';
    source = new EventSource(streamUrl);
    source.addEventListener('snapshot', (event) => {
      const payload = JSON.parse(event.data);
      if (snapshot && payload.html) snapshot.innerHTML = payload.html;
      if (status) {
        const time = new Intl.DateTimeFormat([], {hour: 'numeric', minute: '2-digit', second: '2-digit'}).format(new Date());
        status.textContent = `Live every ${seconds} second${seconds === 1 ? '' : 's'} · updated ${time}`;
      }
    });
    source.addEventListener('error', () => {
      if (status) status.textContent = 'Live connection interrupted; retrying…';
    });
  };

  select?.addEventListener('change', () => {
    const url = new URL(window.location.href);
    url.searchParams.set('refresh', select.value);
    window.history.replaceState({}, '', url);
    startSystemStream();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      closeSystemStream();
      if (status) status.textContent = 'Live updates paused while this tab is hidden.';
    } else {
      startSystemStream();
    }
  });
  window.addEventListener('beforeunload', closeSystemStream);
  startSystemStream();
}
