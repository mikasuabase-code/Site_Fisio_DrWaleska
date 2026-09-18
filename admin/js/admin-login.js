(function () {
  "use strict";

  var form = document.getElementById("loginForm");
  var emailInput = document.getElementById("email");
  var senhaInput = document.getElementById("senha");
  var toggle = document.getElementById("senhaToggle");
  var status = document.getElementById("loginStatus");
  var submit = document.getElementById("loginSubmit");

  function setErro(id, msg) {
    var el = document.getElementById(id + "-error");
    if (el) el.textContent = msg || "";
  }

  function setStatus(msg, tipo) {
    if (!status) return;
    status.textContent = msg || "";
    status.className = "form-status" + (tipo ? " is-" + tipo : "");
  }

  function limparErros() {
    setErro("email", "");
    setErro("senha", "");
    setStatus("");
  }

  if (toggle && senhaInput) {
    toggle.addEventListener("click", function () {
      var mostrando = senhaInput.type === "text";
      senhaInput.type = mostrando ? "password" : "text";
      toggle.setAttribute("aria-label", mostrando ? "Mostrar senha" : "Ocultar senha");
    });
  }

  [emailInput, senhaInput].forEach(function (el) {
    if (!el) return;
    el.addEventListener("input", function () {
      setErro(el.id, "");
      setStatus("");
    });
  });

  function validar() {
    var ok = true;
    var email = (emailInput.value || "").trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setErro("email", "Informe um e-mail válido.");
      ok = false;
    }
    if (!senhaInput.value) {
      setErro("senha", "Informe sua senha.");
      ok = false;
    }
    return ok;
  }

  // Se já houver sessão ativa, vai direto para o painel.
  fetch("/api/admin/me", { headers: { Accept: "application/json" } })
    .then(function (r) {
      if (r.ok) window.location.replace("/admin");
    })
    .catch(function () {});

  if (!form) return;

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    limparErros();
    if (!validar()) return;

    submit.disabled = true;
    setStatus("Entrando...");

    fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailInput.value.trim(),
        senha: senhaInput.value
      })
    })
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, body: body };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.body.ok) {
          throw new Error((res.body && res.body.error) || "Não foi possível entrar. Tente novamente.");
        }
        window.location.replace("/admin#/inicio");
      })
      .catch(function (err) {
        setStatus(err.message || "Não foi possível entrar. Tente novamente.", "error");
        submit.disabled = false;
      });
  });
})();
