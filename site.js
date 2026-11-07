// Oakridge Media site scripts: mobile menu, footer year, copy email, contact form.
(function () {
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? "Close" : "Menu";
    });
  }

  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });

  var copyBtn = document.getElementById("copy-email");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var text = copyBtn.getAttribute("data-copy");
      var done = function () {
        copyBtn.textContent = "Copied";
        setTimeout(function () { copyBtn.textContent = "Copy"; }, 1800);
      };
      var fallback = function () {
        var el = document.getElementById("email-addr");
        var range = document.createRange();
        range.selectNodeContents(el);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        copyBtn.textContent = "Selected, press Ctrl+C";
      };
      try {
        navigator.clipboard.writeText(text).then(done, fallback);
      } catch (e) { fallback(); }
    });
  }

  var form = document.getElementById("contact-form");
  if (form) {
    var status = document.getElementById("form-status");
    var show = function (msg, ok) {
      status.textContent = msg;
      status.classList.toggle("ok", !!ok);
      status.hidden = false;
    };
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.checkValidity()) {
        show("Please fill in your name, a valid email address and a message.");
        return;
      }
      var endpoint = form.getAttribute("data-endpoint");
      if (!endpoint) {
        show("This form isn't connected yet. Please email us at hello@oakridgemedia.com instead.");
        return;
      }
      var btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      fetch(endpoint, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } })
        .then(function (r) {
          if (!r.ok) throw new Error("bad status");
          form.reset();
          show("Thanks, your message was sent. We'll reply within two business days.", true);
        })
        .catch(function () {
          show("Your message couldn't be sent. Please try again, or email hello@oakridgemedia.com.");
        })
        .finally(function () { btn.disabled = false; });
    });
  }
})();
