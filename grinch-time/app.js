(() => {
  const META_URL = "assets/meta.json";
  const TEMPLATE_URL = "assets/template.png";
  const GLOSS_URL = "assets/gloss_overlay.png";

  /** @type {{width:number,height:number,circle:{cx:number,cy:number,radius:number}}} */
  let meta = null;
  /** @type {HTMLImageElement} */
  let templateImg = null;
  /** @type {HTMLImageElement} */
  let glossImg = null;

  /** @type {Map<string, Member>} */
  const members = new Map();

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const pickBtn = document.getElementById("pickBtn");
  const gallery = document.getElementById("gallery");
  const toolbar = document.getElementById("toolbar");
  const downloadAllBtn = document.getElementById("downloadAll");
  const clearAllBtn = document.getElementById("clearAll");
  const countEl = document.getElementById("count");

  /**
   * @typedef {object} Member
   * @property {string} id
   * @property {string} name
   * @property {HTMLImageElement} photo
   * @property {number} scale  cover-relative zoom (>=1)
   * @property {number} offsetX  normalized -1..1
   * @property {number} offsetY  normalized -1..1
   * @property {HTMLCanvasElement} canvas
   * @property {HTMLElement} card
   */

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`Falha ao carregar ${src}`));
      img.src = src;
    });
  }

  async function boot() {
    const [metaRes, tpl, gloss] = await Promise.all([
      fetch(META_URL).then((r) => r.json()),
      loadImage(TEMPLATE_URL),
      loadImage(GLOSS_URL),
    ]);
    meta = metaRes;
    templateImg = tpl;
    glossImg = gloss;
  }

  function coverRect(imgW, imgH, boxW, boxH, scale, offsetX, offsetY) {
    const base = Math.max(boxW / imgW, boxH / imgH);
    const s = base * scale;
    const dw = imgW * s;
    const dh = imgH * s;
    const maxOx = Math.max(0, (dw - boxW) / 2);
    const maxOy = Math.max(0, (dh - boxH) / 2);
    const dx = (boxW - dw) / 2 + offsetX * maxOx;
    const dy = (boxH - dh) / 2 + offsetY * maxOy;
    return { dx, dy, dw, dh };
  }

  /** @param {Member} m */
  function drawMember(m) {
    const { cx, cy, radius: R } = meta.circle;
    const w = meta.width;
    const h = meta.height;
    const ctx = m.canvas.getContext("2d");
    m.canvas.width = w;
    m.canvas.height = h;

    ctx.clearRect(0, 0, w, h);

    // Photo clipped to ornament circle
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.clip();

    const box = R * 2;
    const { dx, dy, dw, dh } = coverRect(
      m.photo.naturalWidth,
      m.photo.naturalHeight,
      box,
      box,
      m.scale,
      m.offsetX,
      m.offsetY
    );
    ctx.drawImage(m.photo, cx - R + dx, cy - R + dy, dw, dh);
    ctx.restore();

    // Grinch template (hole already transparent)
    ctx.drawImage(templateImg, 0, 0, w, h);

    // Soft gloss on top
    ctx.drawImage(glossImg, 0, 0, w, h);
  }

  function basename(filename) {
    return filename.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim() || "foto";
  }

  function slugify(name) {
    return name
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "membro";
  }

  /** @param {File} file */
  async function addFile(file) {
    if (!file.type.startsWith("image/")) return;
    const id = `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`;
    const url = URL.createObjectURL(file);
    const photo = await loadImage(url);

    const canvas = document.createElement("canvas");
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.id = id;

    const preview = document.createElement("div");
    preview.className = "preview-wrap";
    preview.appendChild(canvas);
    preview.title = "Arraste para reposicionar o rosto";

    const body = document.createElement("div");
    body.className = "card-body";

    const nameRow = document.createElement("div");
    nameRow.className = "name-row";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = basename(file.name);
    nameInput.placeholder = "Nome";
    nameInput.setAttribute("aria-label", "Nome do membro");
    nameRow.appendChild(nameInput);

    const controls = document.createElement("div");
    controls.className = "controls";
    const zoomLabel = document.createElement("label");
    zoomLabel.textContent = "Zoom";
    const zoom = document.createElement("input");
    zoom.type = "range";
    zoom.min = "1";
    zoom.max = "2.5";
    zoom.step = "0.01";
    zoom.value = "1.08";
    zoomLabel.appendChild(zoom);
    controls.appendChild(zoomLabel);

    const actions = document.createElement("div");
    actions.className = "actions";
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "btn primary small";
    dl.textContent = "Baixar PNG";
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "btn ghost small";
    rm.textContent = "Remover";
    actions.append(dl, rm);

    body.append(nameRow, controls, actions);
    card.append(preview, body);
    gallery.prepend(card);

    /** @type {Member} */
    const member = {
      id,
      name: nameInput.value,
      photo,
      scale: Number(zoom.value),
      offsetX: 0,
      offsetY: 0,
      canvas,
      card,
    };
    members.set(id, member);
    drawMember(member);
    refreshToolbar();

    nameInput.addEventListener("input", () => {
      member.name = nameInput.value;
    });
    zoom.addEventListener("input", () => {
      member.scale = Number(zoom.value);
      drawMember(member);
    });
    dl.addEventListener("click", () => downloadOne(member));
    rm.addEventListener("click", () => {
      URL.revokeObjectURL(url);
      members.delete(id);
      card.remove();
      refreshToolbar();
    });

    enableDrag(preview, member);
  }

  /** @param {HTMLElement} el @param {Member} m */
  function enableDrag(el, m) {
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onDown = (x, y) => {
      dragging = true;
      lastX = x;
      lastY = y;
    };
    const onMove = (x, y) => {
      if (!dragging) return;
      const rect = el.getBoundingClientRect();
      const scaleX = meta.width / rect.width;
      const scaleY = meta.height / rect.height;
      const dx = (x - lastX) * scaleX;
      const dy = (y - lastY) * scaleY;
      lastX = x;
      lastY = y;
      // Convert pixel drag into normalized offset relative to leftover cover room
      const R = meta.circle.radius;
      const box = R * 2;
      const base = Math.max(box / m.photo.naturalWidth, box / m.photo.naturalHeight);
      const s = base * m.scale;
      const dw = m.photo.naturalWidth * s;
      const dh = m.photo.naturalHeight * s;
      const maxOx = Math.max(1, (dw - box) / 2);
      const maxOy = Math.max(1, (dh - box) / 2);
      m.offsetX = Math.max(-1, Math.min(1, m.offsetX + dx / maxOx));
      m.offsetY = Math.max(-1, Math.min(1, m.offsetY + dy / maxOy));
      drawMember(m);
    };
    const onUp = () => {
      dragging = false;
    };

    el.addEventListener("pointerdown", (e) => {
      el.setPointerCapture(e.pointerId);
      onDown(e.clientX, e.clientY);
    });
    el.addEventListener("pointermove", (e) => onMove(e.clientX, e.clientY));
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  }

  function refreshToolbar() {
    const n = members.size;
    toolbar.hidden = n === 0;
    downloadAllBtn.disabled = n === 0;
    countEl.textContent = n === 0 ? "" : n === 1 ? "1 arte" : `${n} artes`;
  }

  /** @param {Member} m */
  function downloadOne(m) {
    drawMember(m);
    const a = document.createElement("a");
    a.href = m.canvas.toDataURL("image/png");
    a.download = `grinch-${slugify(m.name)}.png`;
    a.click();
  }

  async function downloadZip() {
    if (!window.JSZip) {
      alert("JSZip não carregou. Baixe as artes uma a uma.");
      return;
    }
    downloadAllBtn.disabled = true;
    downloadAllBtn.textContent = "Gerando ZIP…";
    try {
      const zip = new JSZip();
      const used = new Map();
      for (const m of members.values()) {
        drawMember(m);
        let base = slugify(m.name);
        const n = (used.get(base) || 0) + 1;
        used.set(base, n);
        if (n > 1) base = `${base}-${n}`;
        const blob = await new Promise((resolve) => m.canvas.toBlob(resolve, "image/png"));
        zip.file(`grinch-${base}.png`, blob);
      }
      const out = await zip.generateAsync({ type: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(out);
      a.download = "grinch-time.zip";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } finally {
      downloadAllBtn.disabled = members.size === 0;
      downloadAllBtn.textContent = "Baixar todas (ZIP)";
    }
  }

  async function handleFiles(fileList) {
    const files = [...fileList];
    for (const f of files) {
      try {
        await addFile(f);
      } catch (err) {
        console.error(err);
      }
    }
  }

  dropzone.addEventListener("click", (e) => {
    if (e.target === pickBtn) return;
    fileInput.click();
  });
  pickBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files?.length) handleFiles(fileInput.files);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((ev) => {
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer?.files;
    if (files?.length) handleFiles(files);
  });

  downloadAllBtn.addEventListener("click", downloadZip);
  clearAllBtn.addEventListener("click", () => {
    for (const m of members.values()) m.card.remove();
    members.clear();
    refreshToolbar();
  });

  boot().catch((err) => {
    dropzone.innerHTML = `<div class="dropzone-inner"><p>Não deu pra carregar o template: ${err.message}</p></div>`;
  });
})();
