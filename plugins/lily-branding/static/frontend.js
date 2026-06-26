/* Lily branding — rename Odysseus to Lily across the UI */
(function () {
  const NAME = "Lily";
  const OLD = "Odysseus";
  const OLD_LOWER = "odysseus";

  // Text nodes to rebrand — skip internal identifiers, localStorage keys, etc.
  function replaceText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (node.textContent.includes(OLD)) {
        node.textContent = node.textContent.replaceAll(OLD, NAME);
      }
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    // Skip script/style/code elements
    const tag = node.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "CODE" || tag === "PRE") return;

    // Handle placeholder attributes
    if (node.placeholder && node.placeholder.includes(OLD)) {
      node.placeholder = node.placeholder.replaceAll(OLD, NAME);
    }
    // Handle title attributes
    if (node.title && node.title.includes(OLD)) {
      node.title = node.title.replaceAll(OLD, NAME);
    }

    for (const child of node.childNodes) {
      replaceText(child);
    }
  }

  // Rebrand document title
  function fixTitle() {
    if (document.title.includes(OLD)) {
      document.title = document.title.replaceAll(OLD, NAME);
    }
  }

  // Intercept document.title setter
  const titleDesc = Object.getOwnPropertyDescriptor(Document.prototype, "title");
  if (titleDesc && titleDesc.set) {
    Object.defineProperty(document, "title", {
      get: function () {
        return titleDesc.get.call(this);
      },
      set: function (val) {
        if (typeof val === "string" && val.includes(OLD)) {
          val = val.replaceAll(OLD, NAME);
        }
        titleDesc.set.call(this, val);
      },
      configurable: true,
    });
  }

  // Initial pass
  replaceText(document.body);
  fixTitle();

  // Watch for dynamic content
  const observer = new MutationObserver(function (mutations) {
    for (const m of mutations) {
      if (m.type === "childList") {
        for (const node of m.addedNodes) {
          replaceText(node);
        }
      } else if (m.type === "characterData") {
        if (m.target.textContent && m.target.textContent.includes(OLD)) {
          m.target.textContent = m.target.textContent.replaceAll(OLD, NAME);
        }
      } else if (m.type === "attributes") {
        const el = m.target;
        if (m.attributeName === "placeholder" && el.placeholder && el.placeholder.includes(OLD)) {
          el.placeholder = el.placeholder.replaceAll(OLD, NAME);
        }
      }
    }
    fixTitle();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributeFilter: ["placeholder"],
  });

  // Settings tab for future branding customization
  if (window.__odysseusPluginHost) {
    window.__odysseusPluginHost.registerSettingsTab({
      id: "lily-branding",
      label: "Branding",
      render: function () {
        return [
          '<div style="padding: 16px;">',
          "  <h3>Lily Branding</h3>",
          '  <p style="color: var(--text-secondary); margin-top: 8px;">',
          "    Custom branding is active. Future options will include:",
          "  </p>",
          '  <ul style="color: var(--text-secondary); margin-top: 8px; padding-left: 20px;">',
          "    <li>Custom background images</li>",
          "    <li>Theme colors</li>",
          "    <li>Custom logo/avatar</li>",
          "    <li>Welcome screen customization</li>",
          "  </ul>",
          "</div>",
        ].join("\n");
      },
    });
  }
})();
