/* Lily ComfyUI — frontend integration for image generation */
(function () {
  var HOST = window.__odysseusPluginHost;
  if (!HOST) return;

  var LILY_API = "";

  // /imagine slash command — generate images from the chat input
  HOST.registerSlashCommand("/imagine", function (args) {
    if (!args || !args.trim()) {
      HOST.showError("Usage: /imagine <prompt> — describe the image you want");
      return;
    }
    HOST.showToast("Generating image: " + args.substring(0, 60) + "...", { duration: 3000 });
    fetch(LILY_API + "/api/comfyui/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: args.trim() }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok && data.images && data.images.length) {
          HOST.showToast("Image generated (workflow: " + (data.workflow || "text2img") + ")", { duration: 5000 });
        } else {
          HOST.showError("Generation failed: " + (data.error || "unknown error"));
        }
      })
      .catch(function (e) {
        HOST.showError("ComfyUI connection failed: " + e.message);
      });
  });

  // /upscale slash command
  HOST.registerSlashCommand("/upscale", function (args) {
    if (!args || !args.trim()) {
      HOST.showError("Usage: /upscale <image_path>");
      return;
    }
    HOST.showToast("Upscaling image...", { duration: 3000 });
    fetch(LILY_API + "/api/comfyui/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "upscale",
        input_image: args.trim(),
        workflow: "upscale",
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok) {
          HOST.showToast("Upscale complete!", { duration: 5000 });
        } else {
          HOST.showError("Upscale failed: " + (data.error || "unknown error"));
        }
      })
      .catch(function (e) {
        HOST.showError("ComfyUI connection failed: " + e.message);
      });
  });

  // ComfyUI status panel in sidebar
  HOST.registerSidebarItem({
    id: "lily-comfyui",
    label: "ComfyUI",
    icon: '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    onClick: function () {
      HOST.openSettings("plugin-lily-comfyui");
    },
  });

  // Settings tab for ComfyUI management
  HOST.registerSettingsTab({
    id: "lily-comfyui",
    label: "ComfyUI",
    render: function () {
      return [
        '<div style="padding: 16px;" id="comfyui-settings-panel">',
        "  <h3>ComfyUI Image Generation</h3>",
        '  <div id="comfyui-status" style="margin-top: 12px; padding: 12px; border-radius: 8px; background: var(--bg-secondary, #1a1a2e);">',
        '    <span style="color: var(--text-secondary);">Checking status...</span>',
        "  </div>",
        '  <h4 style="margin-top: 20px;">Available Workflows</h4>',
        '  <div id="comfyui-workflows" style="margin-top: 8px;">',
        '    <span style="color: var(--text-secondary);">Loading...</span>',
        "  </div>",
        '  <h4 style="margin-top: 20px;">Quick Generate</h4>',
        '  <div style="margin-top: 8px; display: flex; gap: 8px;">',
        '    <input type="text" id="comfyui-quick-prompt" placeholder="Describe your image..." style="flex: 1; padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border-color, #333); background: var(--bg-primary, #0d0d1a); color: var(--text-primary, #e0e0e0);" />',
        '    <button id="comfyui-quick-generate" style="padding: 8px 16px; border-radius: 6px; border: none; background: var(--accent, #6366f1); color: white; cursor: pointer;">Generate</button>',
        "  </div>",
        '  <div id="comfyui-quick-result" style="margin-top: 12px;"></div>',
        "</div>",
      ].join("\n");
    },
  });

  // Load status and workflows when settings panel becomes visible
  var _statusLoaded = false;
  var observer = new MutationObserver(function () {
    var panel = document.getElementById("comfyui-settings-panel");
    if (!panel || _statusLoaded) return;
    if (panel.offsetParent !== null) {
      _statusLoaded = true;
      _loadStatus();
      _loadWorkflows();
      _bindQuickGenerate();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true, attributes: true });

  function _loadStatus() {
    var el = document.getElementById("comfyui-status");
    if (!el) return;
    fetch(LILY_API + "/api/comfyui/status")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          el.innerHTML = '<span style="color: #f87171;">Offline</span> — ' + _esc(data.error);
        } else {
          el.innerHTML = '<span style="color: #4ade80;">Online</span>';
          if (data.system_stats) {
            var gpu = data.system_stats.system;
            if (gpu && gpu.vram_total) {
              var used = Math.round((gpu.vram_total - gpu.vram_free) / 1024 / 1024);
              var total = Math.round(gpu.vram_total / 1024 / 1024);
              el.innerHTML += " — VRAM: " + used + "/" + total + " MB";
            }
          }
        }
      })
      .catch(function () {
        el.innerHTML = '<span style="color: #f87171;">Connection failed</span>';
      });
  }

  function _loadWorkflows() {
    var el = document.getElementById("comfyui-workflows");
    if (!el) return;
    fetch(LILY_API + "/api/comfyui/workflows")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          el.innerHTML = '<span style="color: var(--text-secondary);">' + _esc(data.error) + "</span>";
          return;
        }
        var workflows = data.workflows || data;
        if (!Array.isArray(workflows) || !workflows.length) {
          el.innerHTML = '<span style="color: var(--text-secondary);">No workflows found</span>';
          return;
        }
        var html = '<div style="display: flex; flex-direction: column; gap: 6px;">';
        workflows.forEach(function (w) {
          var name = typeof w === "string" ? w : w.name || w;
          html +=
            '<div style="padding: 8px 12px; border-radius: 6px; background: var(--bg-primary, #0d0d1a); display: flex; justify-content: space-between; align-items: center;">' +
            '<span style="color: var(--text-primary);">' + _esc(name) + "</span>" +
            "</div>";
        });
        html += "</div>";
        el.innerHTML = html;
      })
      .catch(function () {
        el.innerHTML = '<span style="color: var(--text-secondary);">Could not load workflows</span>';
      });
  }

  function _bindQuickGenerate() {
    var btn = document.getElementById("comfyui-quick-generate");
    var input = document.getElementById("comfyui-quick-prompt");
    var result = document.getElementById("comfyui-quick-result");
    if (!btn || !input) return;

    btn.addEventListener("click", function () {
      var prompt = input.value.trim();
      if (!prompt) return;
      btn.disabled = true;
      btn.textContent = "Generating...";
      if (result) result.innerHTML = '<span style="color: var(--text-secondary);">Generating image...</span>';

      fetch(LILY_API + "/api/comfyui/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          btn.disabled = false;
          btn.textContent = "Generate";
          if (data.ok && data.images && data.images.length) {
            var imgPath = data.images_unix ? data.images_unix[0] : data.images[0];
            if (result) {
              result.innerHTML =
                '<div style="margin-top: 8px;">' +
                '<div style="color: #4ade80; margin-bottom: 8px;">Generated with ' + _esc(data.workflow || "text2img") + " (seed: " + (data.seed || "?") + ")</div>" +
                '<div style="color: var(--text-secondary); font-size: 12px; word-break: break-all;">' + _esc(imgPath) + "</div>" +
                "</div>";
            }
          } else {
            if (result) result.innerHTML = '<span style="color: #f87171;">' + _esc(data.error || "Generation failed") + "</span>";
          }
        })
        .catch(function (e) {
          btn.disabled = false;
          btn.textContent = "Generate";
          if (result) result.innerHTML = '<span style="color: #f87171;">Error: ' + _esc(e.message) + "</span>";
        });
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !btn.disabled) {
        btn.click();
      }
    });
  }

  function _esc(s) {
    var d = document.createElement("div");
    d.textContent = String(s || "");
    return d.innerHTML;
  }
})();
