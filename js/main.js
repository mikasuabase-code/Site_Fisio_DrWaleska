(function () {
  "use strict";

  var ICONS = {
    pilates:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4v16M18 4v16M6 9h12M6 15h12"/></svg>',
    ortopedica:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M5 8l3 2M16 14l3 2M5 16l3-2M16 10l3-2"/><circle cx="12" cy="12" r="2.4"/></svg>',
    rpg:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2.2"/><path d="M12 7.2V14M12 14l-3 6M12 14l3 6M6 10l6 2 6-2"/></svg>',
    miofascial:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12c3-3 6-3 9 0s6 3 9 0"/><path d="M3 17c3-3 6-3 9 0s6 3 9 0"/><path d="M3 7c3-3 6-3 9 0s6 3 9 0"/></svg>',
    gestantes:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4.5" r="2"/><path d="M11 7v5M11 12c0 3 3 4 3 7M11 12H8v6"/></svg>',
    esportiva:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M6 6c3 4 3 8 0 12M18 6c-3 4-3 8 0 12"/></svg>',
    padrao:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'
  };

  var els = {
    servicesGrid: document.getElementById("servicesGrid"),
    servicesLoading: document.getElementById("servicesLoading"),
    servicePickName: document.getElementById("servicePickName"),
    servicoId: document.getElementById("servicoId"),
    chipsDias: document.getElementById("chipsDias"),
    chipsFrequencia: document.getElementById("chipsFrequencia"),
    chipsMotivos: document.getElementById("chipsMotivos"),
    chipsPagamento: document.getElementById("chipsPagamento"),
    nome: document.getElementById("nome"),
    nascimento: document.getElementById("nascimento"),
    telefone: document.getElementById("telefone"),
    submit: document.getElementById("cadastroSubmit"),
    status: document.getElementById("cadastroStatus"),
    success: document.getElementById("cadastroSuccess"),
    successText: document.getElementById("cadastroSuccessText"),
    reset: document.getElementById("cadastroReset"),
    formWrap: document.getElementById("cadastroFormWrap"),
    viewHome: document.getElementById("view-home"),
    viewCadastro: document.getElementById("view-cadastro"),
    navToggle: document.getElementById("navToggle"),
    drawer: document.getElementById("drawer"),
    drawerBackdrop: document.getElementById("drawerBackdrop"),
    drawerClose: document.getElementById("drawerClose"),
    anoAtual: document.getElementById("anoAtual")
  };

  var state = {
    selecionado: null,
    dias: [],
    frequencia: null,
    motivos: [],
    pagamento: null
  };

  function texto(el, msg) {
    if (el) el.textContent = msg || "";
  }

  function moeda(valor) {
    var n = Number(valor || 0);
    return "R$ " + n.toFixed(2).replace(".", ",");
  }

  function erro(id, msg) {
    var el = document.getElementById(id + "-error");
    texto(el, msg);
  }

  function limpaErros() {
    ["nome", "nascimento", "telefone", "dias", "frequencia", "motivos", "pagamento"].forEach(function (id) {
      erro(id, "");
    });
    if (els.status) {
      els.status.textContent = "";
      els.status.className = "form-status";
    }
  }

  function mostrarSucesso(mostrar) {
    if (els.success) els.success.hidden = !mostrar;
    if (els.formWrap) els.formWrap.hidden = !!mostrar;
  }

  function abrirView(id) {
    if (!els.viewHome || !els.viewCadastro) return;
    if (id === "cadastro") {
      els.viewHome.hidden = true;
      els.viewCadastro.hidden = false;
    } else {
      els.viewCadastro.hidden = true;
      els.viewHome.hidden = false;
    }
    if (id !== "cadastro") mostrarSucesso(false);
  }

  function selecionarServico(servico) {
    state.selecionado = servico;
    if (els.servicoId) els.servicoId.value = servico ? servico.id : "";
    texto(els.servicePickName, servico ? servico.nome : "Nenhum serviço selecionado");
    abrirView("cadastro");
    var alvo = document.getElementById("cadastro");
    if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderServicos(servicos) {
    if (!els.servicesGrid) return;
    if (els.servicesLoading) els.servicesLoading.remove();
    if (!servicos.length) {
      els.servicesGrid.innerHTML =
        '<p class="services__loading">Nenhum serviço disponível no momento.</p>';
      return;
    }
    els.servicesGrid.innerHTML = servicos
      .map(function (s) {
        var icone = ICONS[s.icone] || ICONS.padrao;
        return (
          '<article class="service-card">' +
          '<div class="service-card__inner">' +
          '<span class="service-card__icon" aria-hidden="true">' +
          icone +
          "</span>" +
          '<h3 class="service-card__title">' +
          escapeHtml(s.nome) +
          "</h3>" +
          '<p class="service-card__desc">' +
          escapeHtml(s.descricao || "") +
          "</p>" +
          '<div class="service-card__price">' +
          '<span class="service-card__price-value">' +
          moeda(s.valor) +
          "</span>" +
          '<span class="service-card__price-unit">por sessão</span>' +
          "</div>" +
          '<div class="service-card__cta">' +
          '<button class="btn btn--accent btn--sm" type="button" data-servico="' +
          s.id +
          '">Escolher este serviço</button>' +
          "</div>" +
          "</div>" +
          "</article>"
        );
      })
      .join("");

    els.servicesGrid.querySelectorAll("[data-servico]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = Number(btn.getAttribute("data-servico"));
        var servico = servicos.find(function (s) {
          return s.id === id;
        });
        if (servico) selecionarServico(servico);
      });
    });
  }

  function escapeHtml(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderChips(container, opcoes, selecionados, multi) {
    if (!container) return;
    container.innerHTML = opcoes
      .map(function (op) {
        var ativo = selecionados.indexOf(op) !== -1;
        return (
          '<button type="button" class="chip' +
          (ativo ? " is-active" : "") +
          '" data-opcao="' +
          escapeHtml(op) +
          '" aria-pressed="' +
          (ativo ? "true" : "false") +
          '">' +
          escapeHtml(op) +
          "</button>"
        );
      })
      .join("");

    container.querySelectorAll("[data-opcao]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var op = btn.getAttribute("data-opcao");
        if (multi) {
          var i = selecionados.indexOf(op);
          if (i === -1) selecionados.push(op);
          else selecionados.splice(i, 1);
          btn.classList.toggle("is-active");
          btn.setAttribute("aria-pressed", selecionados.indexOf(op) !== -1 ? "true" : "false");
        } else {
          selecionados.length = 0;
          selecionados.push(op);
          container.querySelectorAll("[data-opcao]").forEach(function (b) {
            b.classList.remove("is-active");
            b.setAttribute("aria-pressed", "false");
          });
          btn.classList.add("is-active");
          btn.setAttribute("aria-pressed", "true");
        }
      });
    });
  }

  function carregarConfig() {
    return fetch("/api/cadastro-config")
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        var cfg = (res && res.data) || {};
        var dias = cfg.dias || [];
        var frequencias = cfg.frequencias || [];
        var motivos = cfg.motivos || [];
        renderChips(els.chipsDias, dias, state.dias, true);
        renderChips(els.chipsFrequencia, frequencias, state.frequencia ? [state.frequencia] : [], false);
        renderChips(els.chipsMotivos, motivos, state.motivos, true);
        if (els.chipsFrequencia) {
          els.chipsFrequencia.querySelectorAll("[data-opcao]").forEach(function (btn) {
            btn.addEventListener("click", function () {
              state.frequencia = btn.getAttribute("data-opcao");
            });
          });
        }
      })
      .catch(function () {
        if (els.chipsDias) els.chipsDias.innerHTML = "";
      });
  }

  function carregarServicos() {
    return fetch("/api/services")
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        renderServicos((res && res.data) || []);
      })
      .catch(function () {
        if (els.servicesLoading) els.servicesLoading.remove();
        if (els.servicesGrid) {
          els.servicesGrid.innerHTML =
            '<p class="services__error">Não foi possível carregar os serviços agora. Você ainda pode se cadastrar abaixo.</p>';
        }
      });
  }

  function validar() {
    var ok = true;
    if (!els.nome.value.trim() || els.nome.value.trim().length < 3) {
      erro("nome", "Informe seu nome completo.");
      ok = false;
    }
    if (!els.nascimento.value) {
      erro("nascimento", "Informe sua data de nascimento.");
      ok = false;
    }
    if (!els.telefone.value.trim() || els.telefone.value.replace(/\D/g, "").length < 10) {
      erro("telefone", "Informe um telefone válido.");
      ok = false;
    }
    if (!state.dias.length) {
      erro("dias", "Escolha pelo menos um dia.");
      ok = false;
    }
    if (!state.frequencia) {
      erro("frequencia", "Escolha a frequência desejada.");
      ok = false;
    }
    if (!state.motivos.length) {
      erro("motivos", "Escolha pelo menos um motivo.");
      ok = false;
    }
    if (!state.pagamento) {
      erro("pagamento", "Escolha Pix ou Dinheiro.");
      ok = false;
    }
    if (!state.selecionado) {
      if (els.status) {
        els.status.className = "form-status is-error";
        els.status.textContent = "Escolha um serviço antes de enviar.";
      }
      ok = false;
    }
    return ok;
  }

  function enviar(e) {
    e.preventDefault();
    limpaErros();
    if (!validar()) return;

    var payload = {
      nome: els.nome.value.trim(),
      nascimento: els.nascimento.value,
      telefone: els.telefone.value.trim(),
      servico_id: state.selecionado ? state.selecionado.id : null,
      dias: state.dias,
      frequencia: state.frequencia || "",
      motivos: state.motivos,
      forma_pagamento: state.pagamento
    };

    els.submit.disabled = true;
    if (els.status) {
      els.status.className = "form-status";
      els.status.textContent = "Enviando...";
    }

    fetch("/api/cadastros", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, body: body };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.body.ok) {
          throw new Error((res.body && res.body.error) || "Não foi possível concluir o cadastro. Tente novamente.");
        }
        var d = res.body.data || {};
        mostrarSucesso(true);
        if (els.successText) {
          els.successText.textContent = d.lista_espera
            ? "Cadastro realizado com sucesso. Como o serviço está com lista de espera, entraremos em contato assim que abrir uma vaga."
            : "Cadastro realizado com sucesso. Entraremos em contato para combinar seu atendimento.";
        }
      })
      .catch(function (err) {
        if (els.status) {
          els.status.className = "form-status is-error";
          els.status.textContent = err.message || "Não foi possível concluir o cadastro. Tente novamente.";
        }
      })
      .then(function () {
        els.submit.disabled = false;
      });
  }

  function resetarForm() {
    if (!els.formWrap) return;
    mostrarSucesso(false);
    els.nome.value = "";
    els.nascimento.value = "";
    els.telefone.value = "";
    state.selecionado = null;
    state.dias = [];
    state.frequencia = null;
    state.motivos = [];
    state.pagamento = null;
    if (els.chipsPagamento) {
      els.chipsPagamento.querySelectorAll("[data-pagamento]").forEach(function (b) {
        b.classList.remove("is-active");
        b.setAttribute("aria-pressed", "false");
      });
    }
    if (els.servicoId) els.servicoId.value = "";
    texto(els.servicePickName, "Nenhum serviço selecionado");
    limpaErros();
    carregarConfig();
    abrirView("home");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function abrirDrawer(abrir) {
    if (!els.drawer) return;
    if (abrir) {
      els.drawer.classList.add("is-open");
      if (els.drawerBackdrop) els.drawerBackdrop.classList.add("is-open");
      els.drawer.setAttribute("aria-hidden", "false");
      if (els.navToggle) els.navToggle.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    } else {
      els.drawer.classList.remove("is-open");
      if (els.drawerBackdrop) els.drawerBackdrop.classList.remove("is-open");
      els.drawer.setAttribute("aria-hidden", "true");
      if (els.navToggle) els.navToggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }
  }

  function inicializarReveal() {
    var alvos = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      alvos.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }
    var obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
    );
    alvos.forEach(function (el) {
      obs.observe(el);
    });
  }

  function inicializarNavegacao() {
    document.querySelectorAll('a[href^="#"]').forEach(function (link) {
      link.addEventListener("click", function (ev) {
        var href = link.getAttribute("href");
        if (!href || href === "#") return;
        var alvo = document.querySelector(href);
        if (!alvo) return;
        ev.preventDefault();
        abrirView(href === "#cadastro" ? "cadastro" : "home");
        alvo.scrollIntoView({ behavior: "smooth", block: "start" });
        abrirDrawer(false);
      });
    });

    if (els.navToggle) {
      els.navToggle.addEventListener("click", function () {
        abrirDrawer(!els.drawer.classList.contains("is-open"));
      });
    }
    if (els.drawerClose) {
      els.drawerClose.addEventListener("click", function () {
        abrirDrawer(false);
      });
    }
    if (els.drawerBackdrop) {
      els.drawerBackdrop.addEventListener("click", function () {
        abrirDrawer(false);
      });
    }
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") abrirDrawer(false);
    });
  }

  function inicializar() {
    if (els.anoAtual) els.anoAtual.textContent = new Date().getFullYear();
    mostrarSucesso(false);
    if (els.chipsPagamento) {
      els.chipsPagamento.querySelectorAll("[data-pagamento]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          state.pagamento = btn.getAttribute("data-pagamento");
          els.chipsPagamento.querySelectorAll("[data-pagamento]").forEach(function (b) {
            var ativo = b === btn;
            b.classList.toggle("is-active", ativo);
            b.setAttribute("aria-pressed", ativo ? "true" : "false");
          });
          erro("pagamento", "");
        });
      });
    }
    if (els.nome) {
      els.nome.addEventListener("input", function () {
        erro("nome", "");
      });
    }
    if (els.nascimento) {
      els.nascimento.addEventListener("change", function () {
        erro("nascimento", "");
      });
    }
    if (els.telefone) {
      els.telefone.addEventListener("input", function () {
        erro("telefone", "");
      });
    }
    var form = document.getElementById("cadastroForm");
    if (form) form.addEventListener("submit", enviar);
    if (els.reset) els.reset.addEventListener("click", resetarForm);

    inicializarNavegacao();
    inicializarReveal();
    carregarServicos();
    carregarConfig();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inicializar);
  } else {
    inicializar();
  }
})();
