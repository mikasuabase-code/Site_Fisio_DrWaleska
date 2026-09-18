(function () {
  "use strict";

  /* ============================================================
     Constantes e utilitarios
     ============================================================ */

  var VIEWS = {
    overview: { title: "Olá, Waleska!", sub: "Veja o resumo da sua clínica hoje." },
    agenda: { title: "Agenda", sub: "Atendimentos por dia, semana ou mês." },
    registrations: { title: "Pacientes", sub: "Cadastro único e histórico de cada pessoa." },
    waitlist: { title: "Lista de espera", sub: "Pacientes aguardando vaga no Pilates." },
    duplas: { title: "Duplas", sub: "Formação e acompanhamento das duplas de Pilates." },
    evaluations: { title: "Avaliações", sub: "Avaliação inicial e plano terapêutico." },
    evolutions: { title: "Evoluções", sub: "Registro clínico por atendimento." },
    exercises: { title: "Exercícios", sub: "Biblioteca de exercícios da clínica." },
    services: { title: "Serviços e valores", sub: "Edite os serviços, valores e textos exibidos no site." },
    finance: { title: "Financeiro", sub: "Receitas, pendências e valores recebidos." },
    reports: { title: "Relatórios", sub: "Resumo de pacientes, agenda e financeiro." },
    documents: { title: "Documentos", sub: "Registros e documentos da clínica." },
    comms: { title: "Comunicação", sub: "Contato com pacientes via WhatsApp." },
    users: { title: "Usuários", sub: "Acesso ao painel administrativo." },
    settings: { title: "Configurações", sub: "Conta de acesso e campos do formulário de cadastro." }
  };

  var APT_STATUS_CLASS = {
    "Agendado": "pill--accent",
    "Confirmado": "pill--ok",
    "Realizado": "pill--ok",
    "Cancelado": "pill--muted",
    "Faltou": "pill--muted",
    "Reagendado": "pill--accent"
  };

  var STATUS_CADASTRO = [
    "Novo",
    "Aguardando avaliação",
    "Aguardando dupla",
    "Em atendimento",
    "Lista de espera",
    "Finalizado"
  ];

  var STATUS_ESPERA = ["Lista de espera", "Aguardando dupla", "Em atendimento", "Finalizado"];

  var STATUS_CLASS = {
    "Novo": "pill--accent",
    "Aguardando avaliação": "pill--accent",
    "Aguardando dupla": "pill--accent",
    "Em atendimento": "pill--ok",
    "Lista de espera": "pill--muted",
    "Finalizado": "pill--ok",
    "Em dupla": "pill--ok",
    "Pendente": "pill--accent",
    "Recebido": "pill--ok",
    "Pago": "pill--ok",
    "Cancelado": "pill--muted"
  };

  var state = {
    view: "agenda",
    services: [],
    registrations: [],
    waitlist: [],
    duplas: [],
    cadastroConfig: { dias: [], frequencias: [], motivos: [] },
    duplaPick1: null,
    duplaPick2: null,
    duplaSugestoes: [],
    prontuario: null,
    confirmAction: null,
    agendaView: "week",
    agendaDate: new Date(),
    agendaItems: [],
    aptSuggestTimer: null,
    payPeriodo: ""
  };

  var $ = function (id) {
    return document.getElementById(id);
  };

  function escapeHtml(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function moeda(v) {
    var n = Number(v || 0);
    return "R$ " + n.toFixed(2).replace(".", ",");
  }

  function fmtData(iso) {
    if (!iso) return "—";
    var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return String(iso);
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  function pill(texto) {
    var cls = STATUS_CLASS[texto] || "pill--muted";
    return '<span class="pill ' + cls + '">' + escapeHtml(texto) + "</span>";
  }

  /* ============================================================
     API
     ============================================================ */

  function api(method, url, body) {
    var opts = {
      method: method,
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (r) {
      if (r.status === 401) {
        window.location.replace("/admin-login");
        throw new Error("Sessão expirada.");
      }
      return r.json().then(function (data) {
        if (!r.ok || data.ok === false) {
          throw new Error((data && data.error) || "Não foi possível concluir a operação.");
        }
        return data;
      });
    });
  }

  /* ============================================================
     Toast e modais
     ============================================================ */

  var toastTimer = null;
  function toast(msg, isError) {
    var el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "toast is-visible" + (isError ? " is-error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.className = "toast";
    }, 3200);
  }

  function abrirModal(id) {
    var el = $(id);
    if (!el) return;
    el.classList.add("is-open");
    el.setAttribute("aria-hidden", "false");
  }

  function fecharModal(id) {
    var el = $(id);
    if (!el) return;
    el.classList.remove("is-open");
    el.setAttribute("aria-hidden", "true");
  }

  function confirmar(titulo, texto, onConfirm) {
    $("confirmTitle").textContent = titulo;
    $("confirmText").textContent = texto;
    state.confirmAction = onConfirm;
    abrirModal("modalConfirm");
  }

  document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      fecharModal(btn.getAttribute("data-close-modal"));
    });
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    document.querySelectorAll(".modal.is-open").forEach(function (m) {
      fecharModal(m.id);
    });
  });

  $("btnConfirmAction").addEventListener("click", function () {
    var action = state.confirmAction;
    state.confirmAction = null;
    fecharModal("modalConfirm");
    if (typeof action === "function") action();
  });

  /* ============================================================
     Navegacao (hash routing)
     ============================================================ */

  var ROUTES = {
    "inicio": "overview",
    "visao-geral": "overview",
    "agenda": "agenda",
    "servicos": "services",
    "cadastros": "registrations",
    "pacientes": "registrations",
    "lista-espera": "waitlist",
    "duplas": "duplas",
    "avaliacoes": "evaluations",
    "evolucoes": "evolutions",
    "exercicios": "exercises",
    "financeiro": "finance",
    "relatorios": "reports",
    "documentos": "documents",
    "comunicacao": "comms",
    "usuarios": "users",
    "configuracoes": "settings"
  };

  function aplicarView(nome) {
    if (!VIEWS[nome]) nome = "overview";
    state.view = nome;

    document.querySelectorAll(".admin-view").forEach(function (sec) {
      sec.hidden = sec.getAttribute("data-view-panel") !== nome;
    });
    document.querySelectorAll(".admin-nav__link").forEach(function (link) {
      link.classList.toggle("is-active", link.getAttribute("data-view") === nome);
    });

    $("pageTitle").textContent = VIEWS[nome].title;
    $("pageSubtitle").textContent = VIEWS[nome].sub;
    fecharSidebar();

    if (nome === "overview") carregarOverview();
    if (nome === "agenda") carregarAgenda();
    if (nome === "services") carregarServicos();
    if (nome === "registrations") carregarCadastros();
    if (nome === "waitlist") carregarWaitlist();
    if (nome === "duplas") carregarDuplas();
    if (nome === "evaluations") carregarAvaliacoes();
    if (nome === "evolutions") carregarEvolucoes();
    if (nome === "exercises") carregarExercicios();
    if (nome === "finance") carregarFinanceiro();
    if (nome === "reports") carregarRelatorios();
    if (nome === "documents") carregarDocumentos();
    if (nome === "users") carregarUsuarios();
    if (nome === "comms") carregarComunicacao();
    if (nome === "settings") carregarConfiguracoes();
  }

  function rotaAtual() {
    var hash = (window.location.hash || "").replace(/^#\/?/, "");
    if (!hash) return "overview";
    return ROUTES[hash] || "overview";
  }

  window.addEventListener("hashchange", function () {
    aplicarView(rotaAtual());
  });

  /* ============================================================
     Sidebar mobile
     ============================================================ */

  function abrirSidebar() {
    $("adminSidebar").classList.add("is-open");
    $("adminOverlay").classList.add("is-open");
    $("adminOverlay").setAttribute("aria-hidden", "false");
  }
  function fecharSidebar() {
    $("adminSidebar").classList.remove("is-open");
    $("adminOverlay").classList.remove("is-open");
    $("adminOverlay").setAttribute("aria-hidden", "true");
  }

  $("adminMenuToggle").addEventListener("click", abrirSidebar);
  $("adminOverlay").addEventListener("click", fecharSidebar);
  if ($("adminCollapse")) {
    $("adminCollapse").addEventListener("click", function () {
      document.body.classList.toggle("sidebar-collapsed");
    });
  }
  if ($("btnMobileMore")) {
    $("btnMobileMore").addEventListener("click", abrirSidebar);
  }
  if ($("btnNewAppointmentHome")) {
    $("btnNewAppointmentHome").addEventListener("click", function () {
      withServices(function () { abrirNovoAgendamento(); });
    });
  }
  if ($("btnAgendaTodayHome")) {
    $("btnAgendaTodayHome").addEventListener("click", function () {
      state.agendaDate = new Date();
      carregarAgendaHome();
    });
  }
  document.querySelectorAll("[data-home-cal-view]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.agendaView = btn.getAttribute("data-home-cal-view");
      carregarAgendaHome();
    });
  });
  if ($("globalSearch")) {
    $("globalSearch").addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter") return;
      ev.preventDefault();
      window.location.hash = "#/pacientes";
    });
  }

  /* ============================================================
     Visao geral
     ============================================================ */

  function moedaBr(v) {
    return "R$ " + Number(v || 0).toFixed(2).replace(".", ",");
  }

  function carregarOverview() {
    api("GET", "/api/admin/overview")
      .then(function (res) {
        var d = res.data || {};
        if ($("statAtivos")) $("statAtivos").textContent = d.pacientes_ativos || 0;
        if ($("statHoje")) $("statHoje").textContent = d.atendimentos_hoje || 0;
        if ($("statLista")) $("statLista").textContent = d.lista_espera || 0;
        if ($("statReceita")) $("statReceita").textContent = moedaBr(d.receita_mes);
        if ($("finRecebido")) $("finRecebido").textContent = moedaBr(d.receita_mes);
        if ($("finPendente")) $("finPendente").textContent = moedaBr(d.pendente_mes);
        var totalFin = Number(d.receita_mes || 0) + Number(d.pendente_mes || 0);
        var pct = totalFin ? Math.round((Number(d.receita_mes || 0) / totalFin) * 100) : 0;
        if ($("finBarFill")) $("finBarFill").style.width = pct + "%";
        if ($("sidebarUserName") && d.admin_nome) $("sidebarUserName").textContent = d.admin_nome;
        if ($("sidebarUserRole") && d.admin_role) $("sidebarUserRole").textContent = d.admin_role;
        if ($("pageTitle") && state.view === "overview") {
          $("pageTitle").textContent = "Olá, " + (d.admin_nome || "Waleska").split(" ")[0] + "!";
        }
        renderNext(d.proximos || []);
        renderAlerts(d.alertas || []);
        renderRecentes(d.recentes || []);
        if ($("notifDot")) $("notifDot").hidden = !(d.alertas && d.alertas.length);
        state.agendaView = "week";
        carregarAgendaHome();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function renderNext(items) {
    var el = $("nextAppointments");
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="cal-empty">Nenhum horário à frente.</p>';
      return;
    }
    el.innerHTML = items
      .map(function (it) {
        return (
          '<button type="button" class="side-item" data-apt-id="' +
          it.id +
          '"><strong>' +
          escapeHtml(fmtHora(it.starts_at)) +
          "</strong><span>" +
          escapeHtml(it.patient_name) +
          "</span><small>" +
          escapeHtml(it.service_name || "—") +
          " · " +
          escapeHtml(it.status) +
          "</small></button>"
        );
      })
      .join("");
    el.querySelectorAll("[data-apt-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        abrirAgendamento(Number(btn.getAttribute("data-apt-id")));
      });
    });
  }

  function renderAlerts(items) {
    var el = $("dashAlerts");
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="cal-empty">Nenhum alerta no momento.</p>';
      return;
    }
    el.innerHTML = items
      .map(function (a) {
        return '<a class="side-alert" href="' + escapeHtml(a.href || "#") + '">' + escapeHtml(a.texto) + "</a>";
      })
      .join("");
  }

  function renderRecentes(items) {
    var el = $("recentPatients");
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="cal-empty">Nenhum cadastro recente.</p>';
      return;
    }
    el.innerHTML = items
      .map(function (p) {
        return (
          '<a class="side-item" href="#/pacientes"><strong>' +
          escapeHtml(p.nome) +
          "</strong><small>" +
          escapeHtml(fmtData(p.criadoEm)) +
          " · " +
          escapeHtml(p.status) +
          "</small></a>"
        );
      })
      .join("");
  }

  function carregarAgendaHome() {
    if (!$("homeCalBody")) return;
    var date = ymd(state.agendaDate);
    if ($("homeCalTitle")) $("homeCalTitle").textContent = agendaTitle();
    document.querySelectorAll("[data-home-cal-view]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-home-cal-view") === state.agendaView);
    });
    api("GET", "/api/admin/agenda?view=" + encodeURIComponent(state.agendaView) + "&date=" + encodeURIComponent(date))
      .then(function (res) {
        state.agendaItems = (res.data && res.data.items) || [];
        var orig = $("calBody");
        var tmpId = "homeCalBody";
        var body = $(tmpId);
        if (state.agendaView === "month") renderMonth(body);
        else if (state.agendaView === "week") renderWeek(body);
        else renderDay(body);
        body.querySelectorAll("[data-apt-id]").forEach(function (el) {
          el.addEventListener("click", function (ev) {
            ev.stopPropagation();
            abrirAgendamento(Number(el.getAttribute("data-apt-id")));
          });
        });
        var todayIso = ymd(new Date());
        var todayItems = eventosDoDia(todayIso);
        var mobile = $("mobileTodayList");
        if (mobile) {
          if (!todayItems.length) mobile.innerHTML = '<p class="cal-empty">Sem atendimentos hoje.</p>';
          else {
            mobile.innerHTML = todayItems
              .map(function (it) {
                return (
                  "<p><strong>" +
                  escapeHtml(fmtHora(it.starts_at)) +
                  "</strong> — " +
                  escapeHtml(it.patient_name) +
                  "<br><small>" +
                  escapeHtml(it.service_name || "") +
                  (it.dupla_id ? " — Dupla" : "") +
                  "</small></p>"
                );
              })
              .join("");
          }
        }
      })
      .catch(function () {});
  }

  /* ============================================================
     Servicos
     ============================================================ */

  function carregarServicos() {
    return api("GET", "/api/admin/services")
      .then(function (res) {
        state.services = res.data || [];
        renderServicos();
        preencherFiltroServicos();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function renderServicos() {
    var body = $("servicesTableBody");
    var tabela = $("servicesTable");
    var vazio = $("servicesEmpty");

    if (!state.services.length) {
      body.innerHTML = "";
      tabela.hidden = true;
      vazio.hidden = false;
      $("servicesHint").textContent = "";
      return;
    }
    tabela.hidden = false;
    vazio.hidden = true;
    $("servicesHint").textContent =
      state.services.length + (state.services.length === 1 ? " serviço" : " serviços");

    body.innerHTML = state.services
      .map(function (s) {
        return (
          "<tr>" +
          '<td><span class="cell-strong">' + escapeHtml(s.nome) + "</span>" +
          (s.descricao ? '<div class="cell-muted">' + escapeHtml(s.descricao) + "</div>" : "") +
          "</td>" +
          '<td class="cell-strong">' + moeda(s.valor) + "</td>" +
          '<td class="hide-sm">' + (s.lista_espera ? pill("Lista de espera") : '<span class="cell-muted">Não</span>') + "</td>" +
          "<td>" + (s.ativo ? '<span class="pill pill--ok">Ativo</span>' : '<span class="pill pill--danger">Inativo</span>') + "</td>" +
          '<td class="th-actions"><div class="row-actions">' +
          '<button class="btn btn--outline btn--sm" data-acao="editar-servico" data-id="' + s.id + '">Editar</button>' +
          '<button class="btn btn--danger btn--sm" data-acao="excluir-servico" data-id="' + s.id + '">Excluir</button>' +
          "</div></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function preencherFiltroServicos() {
    var sel = $("regFilterServico");
    if (!sel) return;
    var atual = sel.value;
    sel.innerHTML = '<option value="">Todos os serviços</option>';
    state.services.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = s.nome;
      opt.textContent = s.nome;
      sel.appendChild(opt);
    });
    sel.value = atual;
  }

  function abrirServico(id) {
    var s = state.services.find(function (x) {
      return x.id === id;
    });
    $("serviceModalTitle").textContent = s ? "Editar serviço" : "Novo serviço";
    $("serviceId").value = s ? s.id : "";
    $("sNome").value = s ? s.nome : "";
    $("sDescricao").value = s ? s.descricao : "";
    $("sValor").value = s ? s.valor : "";
    $("sIcone").value = s ? s.icone : "padrao";
    $("sInfoAdicional").value = s ? s.info_adicional : "";
    $("sAtivo").checked = s ? !!s.ativo : true;
    $("sListaEspera").checked = s ? !!s.lista_espera : false;
    $("serviceStatus").textContent = "";
    abrirModal("modalService");
  }

  $("btnNewService").addEventListener("click", function () {
    abrirServico(null);
  });
  $("btnNewServiceEmpty").addEventListener("click", function () {
    abrirServico(null);
  });

  $("servicesTableBody").addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-acao]");
    if (!btn) return;
    var id = Number(btn.getAttribute("data-id"));
    if (btn.getAttribute("data-acao") === "editar-servico") abrirServico(id);
    if (btn.getAttribute("data-acao") === "excluir-servico") {
      var s = state.services.find(function (x) {
        return x.id === id;
      });
      confirmar("Excluir serviço", 'Remover "' + (s ? s.nome : "este serviço") + '"? Esta ação não pode ser desfeita.', function () {
        api("DELETE", "/api/admin/services/" + id)
          .then(function () {
            toast("Serviço removido.");
            carregarServicos();
          })
          .catch(function (err) {
            toast(err.message, true);
          });
      });
    }
  });

  $("serviceForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var id = $("serviceId").value;
    var nome = $("sNome").value.trim();
    if (!nome) {
      $("sNome-error").textContent = "Informe o nome do serviço.";
      return;
    }
    $("sNome-error").textContent = "";

    var payload = {
      nome: nome,
      descricao: $("sDescricao").value.trim(),
      valor: parseFloat($("sValor").value) || 0,
      info_adicional: $("sInfoAdicional").value.trim(),
      icone: $("sIcone").value,
      ativo: $("sAtivo").checked,
      lista_espera: $("sListaEspera").checked
    };

    $("serviceSubmit").disabled = true;
    $("serviceStatus").textContent = "Salvando...";
    var req = id
      ? api("PUT", "/api/admin/services/" + id, payload)
      : api("POST", "/api/admin/services", payload);

    req
      .then(function () {
        fecharModal("modalService");
        toast(id ? "Serviço atualizado." : "Serviço criado.");
        carregarServicos();
      })
      .catch(function (err) {
        $("serviceStatus").textContent = err.message;
        $("serviceStatus").className = "form-status is-error";
      })
      .then(function () {
        $("serviceSubmit").disabled = false;
      });
  });

  /* ============================================================
     Cadastros
     ============================================================ */

  function preencherStatusSelect(sel, lista, valor) {
    sel.innerHTML = "";
    lista.forEach(function (st) {
      var opt = document.createElement("option");
      opt.value = st;
      opt.textContent = st;
      sel.appendChild(opt);
    });
    if (valor) sel.value = valor;
  }

  function carregarCadastros() {
    var q = $("regSearch").value.trim();
    var servico = $("regFilterServico").value;
    var status = $("regFilterStatus").value;
    var params = [];
    if (q) params.push("q=" + encodeURIComponent(q));
    if (servico) params.push("servico=" + encodeURIComponent(servico));
    if (status) params.push("status=" + encodeURIComponent(status));

    return api("GET", "/api/admin/cadastros" + (params.length ? "?" + params.join("&") : ""))
      .then(function (res) {
        state.registrations = res.data || [];
        renderCadastros();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function renderCadastros() {
    var body = $("regTableBody");
    var tabela = $("regTable");
    var vazio = $("regEmpty");
    $("regCount").textContent =
      state.registrations.length +
      (state.registrations.length === 1 ? " cadastro" : " cadastros");

    if (!state.registrations.length) {
      body.innerHTML = "";
      tabela.hidden = true;
      vazio.hidden = false;
      return;
    }
    tabela.hidden = false;
    vazio.hidden = true;

    body.innerHTML = state.registrations
      .map(function (r) {
        return (
          "<tr>" +
          '<td><span class="cell-strong">' + escapeHtml(r.nome) + "</span>" +
          (r.idade != null ? '<div class="cell-muted">' + r.idade + " anos</div>" : "") +
          "</td>" +
          '<td class="cell-muted">' + escapeHtml(r.telefone) + "</td>" +
          '<td class="hide-sm cell-muted">' + escapeHtml(r.servico) + "</td>" +
          '<td class="hide-sm cell-muted">' + fmtData(r.criadoEm) + "</td>" +
          "<td>" + pill(r.status) + "</td>" +
          '<td class="th-actions"><div class="row-actions">' +
          '<button class="btn btn--outline btn--sm" data-acao="ver-cadastro" data-id="' + r.id + '">Ver</button>' +
          '<button class="btn btn--outline btn--sm" data-acao="editar-cadastro" data-id="' + r.id + '">Editar</button>' +
          '<button class="btn btn--danger btn--sm" data-acao="excluir-cadastro" data-id="' + r.id + '">Excluir</button>' +
          "</div></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function linhaDetalhe(label, valor) {
    if (valor == null || valor === "") valor = "—";
    return (
      '<div class="reg-detail__row">' +
      '<span class="reg-detail__label">' + escapeHtml(label) + "</span>" +
      '<span class="reg-detail__value">' + valor + "</span>" +
      "</div>"
    );
  }

  function chips(valores) {
    if (!valores || !valores.length) return "—";
    return (
      '<span class="reg-detail__chips">' +
      valores.map(function (v) {
          return "<span>" + escapeHtml(v) + "</span>";
        })
        .join("") +
      "</span>"
    );
  }

  function abrirDetalheCadastro(id) {
    var r = state.registrations.find(function (x) {
      return x.id === id;
    });
    if (!r) return;
    state.prontuario = { paciente: r, tab: "dados" };
    $("regDetailTitle").textContent = r.nome;
    $("btnEditReg").setAttribute("data-id", r.id);
    document.querySelectorAll("[data-ptab]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-ptab") === "dados");
    });
    renderProntuarioTab("dados");
    abrirModal("modalRegDetail");
    api("GET", "/api/admin/cadastros/" + r.id + "/prontuario")
      .then(function (res) {
        state.prontuario = res.data || state.prontuario;
        state.prontuario.tab = state.prontuario.tab || "dados";
        renderProntuarioTab(state.prontuario.tab);
      })
      .catch(function () {
        var box = $("regDetailBody");
        if (box && state.prontuario.tab !== "dados") {
          box.innerHTML = "<p class='admin-card__sub'>Não foi possível carregar o prontuário.</p>";
        }
      });
  }

  function prontuarioEmpty(txt) {
    return "<p class='admin-card__sub'>" + escapeHtml(txt) + "</p>";
  }

  function prontuarioItems(rows, render) {
    if (!rows || !rows.length) return "";
    return '<div class="prontuario-list">' + rows.map(render).join("") + "</div>";
  }

  function renderProntuarioTab(tab) {
    var p = (state.prontuario && state.prontuario.paciente) || {};
    var body = $("regDetailBody");
    if (!body) return;
    if (tab === "dados") {
      body.innerHTML =
        linhaDetalhe("Nome", escapeHtml(p.nome)) +
        linhaDetalhe("Idade", p.idade != null ? p.idade + " anos" : "—") +
        linhaDetalhe("Nascimento", fmtData(p.nascimento)) +
        linhaDetalhe("Telefone", escapeHtml(p.telefone)) +
        linhaDetalhe("Serviço", escapeHtml(p.servico)) +
        linhaDetalhe("Valor", p.valor != null ? moeda(p.valor) : "—") +
        linhaDetalhe("Forma de pagamento", escapeHtml(p.forma_pagamento || "—")) +
        linhaDetalhe("Dias disponíveis", chips(p.dias)) +
        linhaDetalhe("Frequência", escapeHtml(p.frequencia)) +
        linhaDetalhe("Motivos", chips(p.motivos)) +
        linhaDetalhe("Observações", escapeHtml(p.observacoes)) +
        linhaDetalhe("Status", pill(p.status)) +
        linhaDetalhe("Cadastrado em", fmtData(p.criadoEm));
      return;
    }
    if (tab === "avaliacao") {
      var evals = (state.prontuario && state.prontuario.avaliacoes) || [];
      body.innerHTML = evals.length
        ? prontuarioItems(evals, function (e) {
            return (
              '<article class="prontuario-item"><strong>' + escapeHtml(fmtData(e.evaluated_at)) +
              (e.profissional ? " · " + escapeHtml(e.profissional) : "") +
              "</strong><p>Queixa: " + escapeHtml(e.queixa || "—") +
              "</p><p>Objetivos: " + escapeHtml(e.objetivos || "—") +
              "</p><p>Plano: " + escapeHtml(e.plano || "—") + "</p></article>"
            );
          })
        : prontuarioEmpty("Nenhuma avaliação registrada.");
      return;
    }
    if (tab === "evolucoes") {
      var evos = (state.prontuario && state.prontuario.evolucoes) || [];
      body.innerHTML = evos.length
        ? prontuarioItems(evos, function (e) {
            return (
              '<article class="prontuario-item"><strong>' + escapeHtml(fmtData(e.evolution_date)) +
              (e.profissional ? " · " + escapeHtml(e.profissional) : "") +
              "</strong><p>Procedimentos: " + escapeHtml(e.procedimentos || "—") +
              "</p><p>Exercícios: " + escapeHtml(e.exercicios || "—") +
              "</p><p>Resposta: " + escapeHtml(e.resposta || "—") +
              "</p><p>Próxima conduta: " + escapeHtml(e.proxima_conduta || "—") + "</p></article>"
            );
          })
        : prontuarioEmpty("Nenhuma evolução registrada.");
      return;
    }
    if (tab === "agenda") {
      var agenda = (state.prontuario && state.prontuario.agenda) || [];
      body.innerHTML = agenda.length
        ? prontuarioItems(agenda, function (a) {
            return (
              '<article class="prontuario-item"><strong>' +
              escapeHtml(fmtData(a.starts_at)) + " " + escapeHtml(String(a.starts_at || "").slice(11, 16)) +
              "</strong><p>" + escapeHtml(a.service_name || "—") + " · " + pill(a.status) + "</p></article>"
            );
          })
        : prontuarioEmpty("Nenhum agendamento vinculado.");
      return;
    }
    if (tab === "financeiro") {
      var pays = (state.prontuario && state.prontuario.financeiro) || [];
      var resumo = (state.prontuario && state.prontuario.resumo_financeiro) || {};
      body.innerHTML =
        linhaDetalhe("Recebido", moeda(resumo.recebido)) +
        linhaDetalhe("Pendente", moeda(resumo.pendente)) +
        (pays.length
          ? prontuarioItems(pays, function (pay) {
              return (
                '<article class="prontuario-item"><strong>' +
                escapeHtml(fmtData(pay.criadoEm)) + " · " + moeda(pay.amount) +
                "</strong><p>" + escapeHtml(pay.service_name || "—") + " · " +
                escapeHtml(pay.method || "—") + " · " + pill(pay.status) + "</p></article>"
              );
            })
          : prontuarioEmpty("Nenhum lançamento financeiro."));
      return;
    }
    if (tab === "documentos") {
      var docs = (state.prontuario && state.prontuario.documentos) || [];
      body.innerHTML = docs.length
        ? prontuarioItems(docs, function (d) {
            return (
              '<article class="prontuario-item"><strong>' + escapeHtml(d.titulo) +
              "</strong><p>" + escapeHtml(d.tipo || "Documento") + " · " + escapeHtml(fmtData(d.criadoEm)) + "</p></article>"
            );
          })
        : prontuarioEmpty("Nenhum documento registrado.");
      return;
    }
    if (tab === "exercicios") {
      var evoEx = ((state.prontuario && state.prontuario.evolucoes) || []).filter(function (e) {
        return (e.exercicios || "").trim();
      });
      body.innerHTML = evoEx.length
        ? prontuarioItems(evoEx, function (e) {
            return (
              '<article class="prontuario-item"><strong>' + escapeHtml(fmtData(e.evolution_date)) +
              "</strong><p>" + escapeHtml(e.exercicios) + "</p></article>"
            );
          })
        : prontuarioEmpty("Nenhum exercício vinculado a este paciente.");
      return;
    }
    var hist = [];
    ((state.prontuario && state.prontuario.avaliacoes) || []).forEach(function (e) {
      hist.push({ data: e.evaluated_at, texto: "Avaliação: " + (e.queixa || "registrada") });
    });
    ((state.prontuario && state.prontuario.evolucoes) || []).forEach(function (e) {
      hist.push({ data: e.evolution_date, texto: "Evolução: " + (e.procedimentos || "registrada") });
    });
    ((state.prontuario && state.prontuario.agenda) || []).forEach(function (a) {
      hist.push({ data: a.starts_at, texto: "Agenda: " + (a.service_name || "atendimento") + " · " + (a.status || "") });
    });
    hist.sort(function (a, b) { return String(b.data || "").localeCompare(String(a.data || "")); });
    body.innerHTML = hist.length
      ? prontuarioItems(hist, function (h) {
          return (
            '<article class="prontuario-item"><strong>' + escapeHtml(fmtData(h.data)) +
            "</strong><p>" + escapeHtml(h.texto) + "</p></article>"
          );
        })
      : prontuarioEmpty("Ainda não há histórico clínico.");
  }

  function preencherServicosCadastro(sel, valor) {
    if (!sel) return;
    sel.innerHTML = '<option value="">Selecione</option>';
    state.services.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.nome;
      sel.appendChild(opt);
    });
    if (valor) sel.value = String(valor);
  }

  function abrirNovoCadastro(prefill) {
    prefill = prefill || {};
    withServices(function () {
      $("regNewTitle").textContent = prefill.nome ? "Cadastrar " + prefill.nome : "Novo cadastro";
      $("rnNome").value = prefill.nome || "";
      $("rnNascimento").value = prefill.nascimento || "";
      $("rnTelefone").value = prefill.telefone || "";
      $("rnFrequencia").value = prefill.frequencia || "";
      $("rnObservacoes").value = prefill.observacoes || "";
      $("rnListaEspera").checked = !!prefill.lista_espera;
      if ($("rnPagamento")) $("rnPagamento").value = prefill.forma_pagamento || "";
      $("rnAppointmentIds").value = (prefill.appointment_ids || []).join(",");
      $("regNewStatus").textContent = "";
      $("regNewStatus").className = "form-status";
      preencherStatusSelect($("rnStatus"), STATUS_CADASTRO, prefill.status || "Em atendimento");
      preencherServicosCadastro($("rnServico"), prefill.service_id);
      if (!prefill.service_id && prefill.servico) {
        var match = state.services.find(function (s) {
          return s.nome === prefill.servico;
        });
        if (match) $("rnServico").value = String(match.id);
      }
      fecharModal("modalRegFromAgenda");
      fecharModal("modalAppointment");
      abrirModal("modalRegNew");
      $("rnNome").focus();
    });
  }

  function abrirCadastrosDaAgenda() {
    api("GET", "/api/admin/agenda/sem-cadastro")
      .then(function (res) {
        var list = res.data || [];
        var box = $("regFromAgendaList");
        var empty = $("regFromAgendaEmpty");
        if (!list.length) {
          box.innerHTML = "";
          empty.hidden = false;
        } else {
          empty.hidden = true;
          box.className = "agenda-pending";
          box.innerHTML = list
            .map(function (p) {
              return (
                '<div class="agenda-pending__item">' +
                "<div><strong>" +
                escapeHtml(p.nome) +
                "</strong><small>" +
                escapeHtml(p.servico || "Sem serviço") +
                " · " +
                p.appointments_count +
                (p.appointments_count === 1 ? " agendamento" : " agendamentos") +
                "</small></div>" +
                '<button class="btn btn--primary btn--sm" type="button" data-acao="cadastrar-agenda" data-nome="' +
                escapeHtml(p.nome) +
                '" data-servico="' +
                escapeHtml(p.servico || "") +
                '" data-sid="' +
                (p.service_id || "") +
                '" data-ids="' +
                (p.appointment_ids || []).join(",") +
                '">Criar cadastro</button></div>'
              );
            })
            .join("");
        }
        abrirModal("modalRegFromAgenda");
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function abrirEdicaoCadastro(id) {
    var r = state.registrations.find(function (x) {
      return x.id === id;
    });
    if (!r) return;
    $("regEditId").value = r.id;
    $("reNome").value = r.nome;
    $("reNascimento").value = r.nascimento || "";
    $("reTelefone").value = r.telefone;
    preencherStatusSelect($("reStatus"), STATUS_CADASTRO, r.status);
    $("reFrequencia").value = r.frequencia || "";
    $("reObservacoes").value = r.observacoes || "";
    $("regEditStatus").textContent = "";
    fecharModal("modalRegDetail");
    abrirModal("modalRegEdit");
  }

  $("regTableBody").addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-acao]");
    if (!btn) return;
    var id = Number(btn.getAttribute("data-id"));
    var acao = btn.getAttribute("data-acao");
    if (acao === "ver-cadastro") abrirDetalheCadastro(id);
    if (acao === "editar-cadastro") abrirEdicaoCadastro(id);
    if (acao === "excluir-cadastro") {
      var r = state.registrations.find(function (x) {
        return x.id === id;
      });
      confirmar("Excluir cadastro", 'Remover o cadastro de "' + (r ? r.nome : "esta pessoa") + '"?', function () {
        api("DELETE", "/api/admin/cadastros/" + id)
          .then(function () {
            toast("Cadastro removido.");
            carregarCadastros();
          })
          .catch(function (err) {
            toast(err.message, true);
          });
      });
    }
  });

  $("btnNewReg").addEventListener("click", function () {
    abrirNovoCadastro();
  });
  $("btnNewRegEmpty").addEventListener("click", function () {
    abrirNovoCadastro();
  });
  $("btnRegFromAgenda").addEventListener("click", abrirCadastrosDaAgenda);
  $("btnAgendaCreateReg").addEventListener("click", abrirCadastrosDaAgenda);

  $("regFromAgendaList").addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-acao='cadastrar-agenda']");
    if (!btn) return;
    var ids = (btn.getAttribute("data-ids") || "")
      .split(",")
      .map(function (v) {
        return Number(v);
      })
      .filter(Boolean);
    abrirNovoCadastro({
      nome: btn.getAttribute("data-nome") || "",
      servico: btn.getAttribute("data-servico") || "",
      service_id: btn.getAttribute("data-sid") || "",
      appointment_ids: ids,
      status: "Em atendimento"
    });
  });

  $("regNewForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var status = $("regNewStatus");
    var nome = $("rnNome").value.trim();
    var telefone = $("rnTelefone").value.trim();
    var servicoSel = $("rnServico");
    if (!nome || !telefone) {
      status.textContent = "Nome e telefone são obrigatórios.";
      status.className = "form-status is-error";
      return;
    }
    if (!servicoSel.value) {
      status.textContent = "Selecione um serviço.";
      status.className = "form-status is-error";
      return;
    }
    var ids = ($("rnAppointmentIds").value || "")
      .split(",")
      .map(function (v) {
        return Number(v);
      })
      .filter(Boolean);
    var payload = {
      nome: nome,
      nascimento: $("rnNascimento").value || null,
      telefone: telefone,
      servico_id: Number(servicoSel.value),
      status: $("rnStatus").value || "Em atendimento",
      frequencia: $("rnFrequencia").value,
      observacoes: $("rnObservacoes").value.trim(),
      lista_espera: $("rnListaEspera").checked,
      forma_pagamento: $("rnPagamento") ? $("rnPagamento").value : "",
      appointment_ids: ids
    };
    api("POST", "/api/admin/cadastros", payload)
      .then(function () {
        fecharModal("modalRegNew");
        toast("Cadastro criado.");
        if (state.view === "registrations") carregarCadastros();
        if (state.view === "agenda") carregarAgenda();
        if (state.view === "waitlist") carregarWaitlist();
      })
      .catch(function (err) {
        status.textContent = err.message;
        status.className = "form-status is-error";
      });
  });

  document.querySelectorAll("[data-ptab]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var tab = btn.getAttribute("data-ptab");
      if (state.prontuario) state.prontuario.tab = tab;
      document.querySelectorAll("[data-ptab]").forEach(function (b) {
        b.classList.toggle("is-active", b === btn);
      });
      renderProntuarioTab(tab);
    });
  });

  $("btnEditReg").addEventListener("click", function () {
    abrirEdicaoCadastro(Number(this.getAttribute("data-id")));
  });

  $("regEditForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var id = $("regEditId").value;
    var payload = {
      nome: $("reNome").value.trim(),
      nascimento: $("reNascimento").value || null,
      telefone: $("reTelefone").value.trim(),
      status: $("reStatus").value,
      frequencia: $("reFrequencia").value,
      observacoes: $("reObservacoes").value.trim()
    };
    if (!payload.nome || !payload.telefone) {
      $("regEditStatus").textContent = "Nome e telefone são obrigatórios.";
      $("regEditStatus").className = "form-status is-error";
      return;
    }
    api("PUT", "/api/admin/cadastros/" + id, payload)
      .then(function () {
        fecharModal("modalRegEdit");
        toast("Cadastro atualizado.");
        carregarCadastros();
      })
      .catch(function (err) {
        $("regEditStatus").textContent = err.message;
        $("regEditStatus").className = "form-status is-error";
      });
  });

  var regDebounce = null;
  ["regSearch", "regFilterServico", "regFilterStatus"].forEach(function (id) {
    var el = $(id);
    if (!el) return;
    var evt = el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(evt, function () {
      clearTimeout(regDebounce);
      regDebounce = setTimeout(carregarCadastros, 260);
    });
  });

  /* ============================================================
     Lista de espera
     ============================================================ */

  function carregarWaitlist() {
    var q = $("wlSearch").value.trim();
    var status = $("wlFilterStatus").value;
    var params = [];
    if (q) params.push("q=" + encodeURIComponent(q));
    if (status) params.push("status=" + encodeURIComponent(status));

    return api("GET", "/api/admin/lista-espera" + (params.length ? "?" + params.join("&") : ""))
      .then(function (res) {
        state.waitlist = res.data || [];
        renderWaitlist();
        actualizarBadges();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function renderWaitlist() {
    var body = $("wlTableBody");
    var tabela = $("wlTable");
    var vazio = $("wlEmpty");
    $("wlCount").textContent =
      state.waitlist.length + (state.waitlist.length === 1 ? " pessoa" : " pessoas");

    if (!state.waitlist.length) {
      body.innerHTML = "";
      tabela.hidden = true;
      vazio.hidden = false;
      return;
    }
    tabela.hidden = false;
    vazio.hidden = true;

    body.innerHTML = state.waitlist
      .map(function (w) {
        return (
          "<tr>" +
          '<td><span class="cell-strong">' + escapeHtml(w.nome) + "</span>" +
          (w.idade != null ? '<div class="cell-muted">' + w.idade + " anos</div>" : "") +
          "</td>" +
          '<td class="cell-muted">' + escapeHtml(w.telefone) + "</td>" +
          '<td class="hide-sm cell-muted">' + fmtData(w.criadoEm) + "</td>" +
          "<td>" + pill(w.status) + "</td>" +
          '<td class="th-actions"><div class="row-actions">' +
          '<button class="btn btn--outline btn--sm" data-acao="editar-espera" data-id="' + w.id + '">Editar</button>' +
          '<button class="btn btn--danger btn--sm" data-acao="excluir-espera" data-id="' + w.id + '">Remover</button>' +
          "</div></td>" +
          "</tr>"
        );
      })
      .join("");
  }

  function abrirEdicaoEspera(id) {
    var w = state.waitlist.find(function (x) {
      return x.id === id;
    });
    if (!w) return;
    $("wlEditId").value = w.id;
    $("weNome").value = w.nome;
    $("weNascimento").value = w.nascimento || "";
    $("weTelefone").value = w.telefone;
    preencherStatusSelect($("weStatus"), STATUS_ESPERA, w.status);
    $("weDificuldades").value = w.dificuldades || w.observacoes || "";
    $("wlEditStatus").textContent = "";
    abrirModal("modalWlEdit");
  }

  $("wlTableBody").addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-acao]");
    if (!btn) return;
    var id = Number(btn.getAttribute("data-id"));
    if (btn.getAttribute("data-acao") === "editar-espera") abrirEdicaoEspera(id);
    if (btn.getAttribute("data-acao") === "excluir-espera") {
      var w = state.waitlist.find(function (x) {
        return x.id === id;
      });
      confirmar("Remover da lista", 'Remover "' + (w ? w.nome : "esta pessoa") + '" da lista de espera?', function () {
        api("DELETE", "/api/admin/lista-espera/" + id)
          .then(function () {
            toast("Removido da lista de espera.");
            carregarWaitlist();
          })
          .catch(function (err) {
            toast(err.message, true);
          });
      });
    }
  });

  $("wlEditForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var id = $("wlEditId").value;
    var payload = {
      nome: $("weNome").value.trim(),
      nascimento: $("weNascimento").value || null,
      telefone: $("weTelefone").value.trim(),
      status: $("weStatus").value,
      dificuldades: $("weDificuldades").value.trim()
    };
    if (!payload.nome || !payload.telefone) {
      $("wlEditStatus").textContent = "Nome e telefone são obrigatórios.";
      $("wlEditStatus").className = "form-status is-error";
      return;
    }
    api("PUT", "/api/admin/lista-espera/" + id, payload)
      .then(function () {
        fecharModal("modalWlEdit");
        toast("Paciente atualizado.");
        carregarWaitlist();
      })
      .catch(function (err) {
        $("wlEditStatus").textContent = err.message;
        $("wlEditStatus").className = "form-status is-error";
      });
  });

  var wlDebounce = null;
  ["wlSearch", "wlFilterStatus"].forEach(function (id) {
    var el = $(id);
    if (!el) return;
    var evt = el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(evt, function () {
      clearTimeout(wlDebounce);
      wlDebounce = setTimeout(carregarWaitlist, 260);
    });
  });

  /* ============================================================
     Duplas
     ============================================================ */

  function carregarDuplas() {
    return Promise.all([
      api("GET", "/api/admin/duplas"),
      api("GET", "/api/admin/duplas/sugestoes").catch(function () {
        return { data: [], candidatos: 0 };
      })
    ])
      .then(function (results) {
        state.duplas = (results[0] && results[0].data) || [];
        state.duplaSugestoes = (results[1] && results[1].data) || [];
        state.duplaCandidatos = (results[1] && results[1].candidatos) || 0;
        renderDuplas();
        renderDuplaSugestoes();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  function renderDuplas() {
    var grid = $("duplasGrid");
    var vazio = $("duplasEmpty");
    $("duplasHint").textContent =
      state.duplas.length + (state.duplas.length === 1 ? " dupla" : " duplas");

    if (!state.duplas.length) {
      grid.innerHTML = "";
      vazio.hidden = false;
      return;
    }
    vazio.hidden = true;
    grid.innerHTML = state.duplas
      .map(function (d) {
        var p1 = d.paciente1 || {};
        var p2 = d.paciente2 || {};
        return (
          '<article class="dupla-card">' +
          '<div class="dupla-card__pair">' +
          '<span class="dupla-card__name">' + escapeHtml(p1.nome) + "</span>" +
          '<span class="dupla-card__plus">+</span>' +
          '<span class="dupla-card__name">' + escapeHtml(p2.nome) + "</span>" +
          "</div>" +
          '<div class="dupla-card__meta">' +
          "<span>" + escapeHtml(d.servico) + "</span>" +
          (p1.idade != null ? "<span>" + p1.idade + " e " + (p2.idade != null ? p2.idade : "—") + " anos</span>" : "") +
          "<span>" + escapeHtml(p1.telefone || "") + "</span>" +
          "<span>criada em " + fmtData(d.criadaEm) + "</span>" +
          "</div>" +
          '<div class="dupla-card__footer">' +
          pill(d.status) +
          '<div class="row-actions">' +
          '<button class="btn btn--outline btn--sm" data-acao="ver-dupla" data-id="' + d.id + '">Detalhes</button>' +
          '<button class="btn btn--danger btn--sm" data-acao="desfazer-dupla" data-id="' + d.id + '">Desfazer</button>' +
          "</div>" +
          "</div>" +
          "</article>"
        );
      })
      .join("");
  }

  function renderPickers() {
    [1, 2].forEach(function (n) {
      var box = $("duplaPicker" + n);
      var pick = n === 1 ? state.duplaPick1 : state.duplaPick2;
      if (!state.waitlist.length) {
        box.innerHTML = '<p class="dupla-picker__empty">Nenhum paciente na lista de espera.</p>';
        return;
      }
      box.innerHTML = state.waitlist
        .map(function (w) {
          var picked = pick === w.id ? " is-picked" : "";
          return (
            '<button type="button" class="dupla-option' + picked + '" data-pick="' + n + '" data-id="' + w.id + '">' +
            escapeHtml(w.nome) +
            "<small>" + escapeHtml(w.servico) + (w.idade != null ? " · " + w.idade + " anos" : "") + "</small>" +
            "</button>"
          );
        })
        .join("");
    });
  }

  function abrirNovaDupla() {
    state.duplaPick1 = null;
    state.duplaPick2 = null;
    $("duplaObservacoes").value = "";
    $("duplaStatus").textContent = "";
    $("duplaSuggestion").hidden = true;

    carregarWaitlist().then(function () {
      if (!state.waitlist.length) {
        renderPickers();
        $("duplaStatus").textContent = "A lista de espera está vazia no momento.";
        $("duplaStatus").className = "form-status";
        return;
      }
      renderPickers();
      sugerirDupla();
    });
    abrirModal("modalNewDupla");
  }

  function checksHtml(checks) {
    return (
      '<ul class="dupla-suggest__checks">' +
      (checks || [])
        .map(function (c) {
          return (
            '<li class="' + (c.ok ? "is-ok" : "is-no") + '">' +
            (c.ok ? "✓ " : "× ") +
            escapeHtml(c.texto) +
            "</li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function renderDuplaSugestoes() {
    var grid = $("duplasSuggestGrid");
    var vazio = $("duplasSuggestEmpty");
    var hint = $("duplasSuggestHint");
    var items = state.duplaSugestoes || [];
    if (hint) {
      hint.textContent = items.length
        ? items.length + (items.length === 1 ? " sugestão" : " sugestões")
        : (state.duplaCandidatos || 0) + " pessoa(s) na lista";
    }
    if (!grid) return;
    if (!items.length) {
      grid.innerHTML = "";
      if (vazio) vazio.hidden = false;
      return;
    }
    if (vazio) vazio.hidden = true;
    grid.innerHTML = items
      .map(function (s, idx) {
        var p1 = s.paciente1 || {};
        var p2 = s.paciente2 || {};
        return (
          '<article class="dupla-suggest">' +
          '<div class="dupla-suggest__pair">' +
          escapeHtml(p1.nome) + " + " + escapeHtml(p2.nome) +
          "</div>" +
          '<div class="dupla-suggest__score dupla-suggest__score--' + escapeHtml(s.nivel || "media") + '">' +
          escapeHtml(s.rotulo || "Compatibilidade") + " · " + (s.score || 0) + "%" +
          "</div>" +
          checksHtml(s.checks) +
          '<div class="dupla-suggest__actions">' +
          '<button class="btn btn--primary btn--sm" type="button" data-aprovar-sugestao="' + idx + '">Aprovar sugestão</button>' +
          '<button class="btn btn--outline btn--sm" type="button" data-usar-sugestao="' + idx + '">Ajustar</button>' +
          "</div>" +
          "</article>"
        );
      })
      .join("");
  }

  function usarSugestao(idx, aprovar) {
    var s = (state.duplaSugestoes || [])[idx];
    if (!s) return;
    state.duplaPick1 = s.paciente1_id;
    state.duplaPick2 = s.paciente2_id;
    if (aprovar) {
      confirmar(
        "Aprovar dupla",
        (s.paciente1 && s.paciente1.nome ? s.paciente1.nome : "Paciente 1") +
          " + " +
          (s.paciente2 && s.paciente2.nome ? s.paciente2.nome : "Paciente 2") +
          ". Confirma a formação desta dupla?",
        function () {
          api("POST", "/api/admin/duplas", {
            paciente1_id: s.paciente1_id,
            paciente2_id: s.paciente2_id,
            observacoes: "Aprovada a partir de sugestão automática"
          })
            .then(function () {
              toast("Dupla formada.");
              carregarDuplas();
            })
            .catch(function (err) {
              toast(err.message, true);
            });
        }
      );
      return;
    }
    carregarWaitlist().then(function () {
      renderPickers();
      $("duplaObservacoes").value = "";
      $("duplaStatus").textContent = "";
      var aviso = $("duplaSuggestion");
      aviso.hidden = false;
      aviso.innerHTML =
        "<strong>" + escapeHtml(s.rotulo || "Sugestão") + ".</strong> " +
        "Revise os dois pacientes e confirme a dupla.";
      abrirModal("modalNewDupla");
    });
  }

  function sugerirDupla() {
    var aviso = $("duplaSuggestion");
    if (state.waitlist.length < 2) {
      aviso.hidden = true;
      return;
    }
    aviso.hidden = false;
    aviso.innerHTML =
      "<strong>" + state.waitlist.length + " pessoas na lista de espera.</strong> " +
      "Selecione dois pacientes ou volte à tela de Duplas para ver as sugestões automáticas.";
  }

  $("btnNewDupla").addEventListener("click", abrirNovaDupla);
  $("btnNewDuplaEmpty").addEventListener("click", abrirNovaDupla);

  if ($("duplasSuggestGrid")) {
    $("duplasSuggestGrid").addEventListener("click", function (ev) {
      var aprovar = ev.target.closest("[data-aprovar-sugestao]");
      var ajustar = ev.target.closest("[data-usar-sugestao]");
      if (aprovar) usarSugestao(Number(aprovar.getAttribute("data-aprovar-sugestao")), true);
      if (ajustar) usarSugestao(Number(ajustar.getAttribute("data-usar-sugestao")), false);
    });
  }

  document.querySelectorAll("#duplaPicker1, #duplaPicker2").forEach(function (box) {
    box.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-pick]");
      if (!btn) return;
      var n = Number(btn.getAttribute("data-pick"));
      var id = Number(btn.getAttribute("data-id"));
      if (n === 1) state.duplaPick1 = state.duplaPick1 === id ? null : id;
      if (n === 2) state.duplaPick2 = state.duplaPick2 === id ? null : id;
      renderPickers();
    });
  });

  $("btnConfirmDupla").addEventListener("click", function () {
    if (!state.duplaPick1 || !state.duplaPick2) {
      $("duplaStatus").textContent = "Selecione os dois pacientes.";
      $("duplaStatus").className = "form-status is-error";
      return;
    }
    if (state.duplaPick1 === state.duplaPick2) {
      $("duplaStatus").textContent = "Os dois pacientes devem ser diferentes.";
      $("duplaStatus").className = "form-status is-error";
      return;
    }

    var p1 = state.waitlist.find(function (w) {
      return w.id === state.duplaPick1;
    });
    var p2 = state.waitlist.find(function (w) {
      return w.id === state.duplaPick2;
    });

    $("duplaConfirmBody").innerHTML =
      linhaDetalhe("Paciente 1", escapeHtml(p1 ? p1.nome : "—")) +
      linhaDetalhe("Paciente 2", escapeHtml(p2 ? p2.nome : "—")) +
      linhaDetalhe("Serviço", escapeHtml(p1 && p2 && p1.servico === p2.servico ? p1.servico : (p1 ? p1.servico : "") + " / " + (p2 ? p2.servico : "")));
    fecharModal("modalNewDupla");
    abrirModal("modalConfirmDupla");
  });

  $("btnSubmitDupla").addEventListener("click", function () {
    var payload = {
      paciente1_id: state.duplaPick1,
      paciente2_id: state.duplaPick2,
      observacoes: $("duplaObservacoes").value.trim()
    };
    $("btnSubmitDupla").disabled = true;
    api("POST", "/api/admin/duplas", payload)
      .then(function () {
        fecharModal("modalConfirmDupla");
        toast("Dupla criada.");
        carregarDuplas();
      })
      .catch(function (err) {
        fecharModal("modalConfirmDupla");
        toast(err.message, true);
      })
      .then(function () {
        $("btnSubmitDupla").disabled = false;
      });
  });

  function abrirDetalheDupla(id) {
    var d = state.duplas.find(function (x) {
      return x.id === id;
    });
    if (!d) return;
    var p1 = d.paciente1 || {};
    var p2 = d.paciente2 || {};
    $("duplaDetailId").value = d.id;
    $("duplaDetailBody").innerHTML =
      linhaDetalhe("Paciente 1", escapeHtml(p1.nome) + (p1.idade != null ? " · " + p1.idade + " anos" : "")) +
      linhaDetalhe("Telefone 1", escapeHtml(p1.telefone)) +
      linhaDetalhe("Paciente 2", escapeHtml(p2.nome) + (p2.idade != null ? " · " + p2.idade + " anos" : "")) +
      linhaDetalhe("Telefone 2", escapeHtml(p2.telefone)) +
      linhaDetalhe("Serviço", escapeHtml(d.servico)) +
      linhaDetalhe("Criada em", fmtData(d.criadaEm));
    $("ddObservacoes").value = d.observacoes || "";
    $("ddStatus").value = d.status;
    $("duplaDetailStatus").textContent = "";
    abrirModal("modalDuplaDetail");
  }

  $("duplasGrid").addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-acao]");
    if (!btn) return;
    var id = Number(btn.getAttribute("data-id"));
    if (btn.getAttribute("data-acao") === "ver-dupla") abrirDetalheDupla(id);
    if (btn.getAttribute("data-acao") === "desfazer-dupla") {
      confirmar(
        "Desfazer dupla",
        "Os dois pacientes voltam para a lista de espera. Deseja continuar?",
        function () {
          api("DELETE", "/api/admin/duplas/" + id)
            .then(function () {
              toast("Dupla desfeita.");
              carregarDuplas();
            })
            .catch(function (err) {
              toast(err.message, true);
            });
        }
      );
    }
  });

  $("duplaDetailForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var id = $("duplaDetailId").value;
    api("PUT", "/api/admin/duplas/" + id, {
      observacoes: $("ddObservacoes").value.trim(),
      status: $("ddStatus").value
    })
      .then(function () {
        fecharModal("modalDuplaDetail");
        toast("Dupla atualizada.");
        carregarDuplas();
      })
      .catch(function (err) {
        $("duplaDetailStatus").textContent = err.message;
        $("duplaDetailStatus").className = "form-status is-error";
      });
  });

  $("btnUndoDupla").addEventListener("click", function () {
    var id = Number($("duplaDetailId").value);
    fecharModal("modalDuplaDetail");
    confirmar("Desfazer dupla", "Os dois pacientes voltam para a lista de espera. Deseja continuar?", function () {
      api("DELETE", "/api/admin/duplas/" + id)
        .then(function () {
          toast("Dupla desfeita.");
          carregarDuplas();
        })
        .catch(function (err) {
          toast(err.message, true);
        });
    });
  });

  /* ============================================================
     Configuracoes
     ============================================================ */

  function preencherClinica(data) {
    data = data || {};
    if ($("setClinicaNome")) $("setClinicaNome").value = data.nome || "";
    if ($("setWhatsapp")) $("setWhatsapp").value = data.whatsapp || "";
    if ($("setClinicaEmail")) $("setClinicaEmail").value = data.email_clinica || data.email || "";
    if ($("setEndereco")) $("setEndereco").value = data.endereco || "";
    if ($("setHorarios")) $("setHorarios").value = data.horarios || "";
    if ($("setCrefito")) $("setCrefito").value = data.crefito || "";
    if ($("commsWhatsapp") && data.whatsapp_link) $("commsWhatsapp").href = data.whatsapp_link;
  }

  function carregarComunicacao() {
    api("GET", "/api/admin/config")
      .then(function (res) {
        var d = res.data || {};
        if ($("commsWhatsapp") && d.whatsapp_link) $("commsWhatsapp").href = d.whatsapp_link;
      })
      .catch(function () {});
  }

  function carregarConfiguracoes() {
    api("GET", "/api/admin/config")
      .then(function (res) {
        var d = res.data || {};
        $("setEmail").value = d.email || "";
        preencherClinica(d);
      })
      .catch(function (err) {
        toast(err.message, true);
      });

    api("GET", "/api/admin/cadastro-config")
      .then(function (res) {
        state.cadastroConfig = res.data || { dias: [], frequencias: [], motivos: [] };
        renderConfigEditor();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
  }

  var CONFIG_GRUPOS = [
    { chave: "dias", titulo: "Dias disponíveis" },
    { chave: "frequencias", titulo: "Frequências" },
    { chave: "motivos", titulo: "Principais motivos" }
  ];

  function renderConfigEditor() {
    var box = $("cadastroConfigEditor");
    box.innerHTML = CONFIG_GRUPOS.map(function (g) {
      var valores = state.cadastroConfig[g.chave] || [];
      return (
        '<div class="config-group" data-grupo="' + g.chave + '">' +
        '<div class="config-group__head"><span class="config-group__title">' + g.titulo + "</span></div>" +
        '<div class="config-tags">' +
        valores
          .map(function (v) {
            return (
              '<span class="config-tag">' + escapeHtml(v) +
              '<button type="button" data-remove="' + escapeHtml(v) + '" aria-label="Remover">×</button></span>'
            );
          })
          .join("") +
        "</div>" +
        '<div class="config-add">' +
        '<input class="admin-input" type="text" data-novo="' + g.chave + '" placeholder="Adicionar opção...">' +
        '<button class="btn btn--accent btn--sm" type="button" data-add="' + g.chave + '">Adicionar</button>' +
        "</div>" +
        "</div>"
      );
    }).join("");
  }

  $("cadastroConfigEditor").addEventListener("click", function (ev) {
    var remover = ev.target.closest("[data-remove]");
    if (remover) {
      var grupo = remover.closest("[data-grupo]").getAttribute("data-grupo");
      var valor = remover.getAttribute("data-remove");
      state.cadastroConfig[grupo] = (state.cadastroConfig[grupo] || []).filter(function (v) {
        return v !== valor;
      });
      renderConfigEditor();
      return;
    }
    var add = ev.target.closest("[data-add]");
    if (add) {
      var chave = add.getAttribute("data-add");
      var input = document.querySelector('[data-novo="' + chave + '"]');
      var novo = (input.value || "").trim();
      if (!novo) return;
      var lista = state.cadastroConfig[chave] || [];
      if (lista.indexOf(novo) === -1) lista.push(novo);
      state.cadastroConfig[chave] = lista;
      renderConfigEditor();
    }
  });

  $("cadastroConfigSave").addEventListener("click", function () {
    var status = $("cadastroConfigStatus");
    var payload = {
      dias: state.cadastroConfig.dias || [],
      frequencias: state.cadastroConfig.frequencias || [],
      motivos: state.cadastroConfig.motivos || []
    };
    api("PUT", "/api/admin/cadastro-config", payload)
      .then(function () {
        status.textContent = "Campos salvos.";
        status.className = "form-status is-success";
        toast("Campos do cadastro atualizados.");
      })
      .catch(function (err) {
        status.textContent = err.message;
        status.className = "form-status is-error";
      });
  });

  $("settingsForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var status = $("settingsStatus");
    var payload = {
      email: $("setEmail").value.trim(),
      senha_atual: $("setSenhaAtual").value,
      nova_senha: $("setNovaSenha").value,
      confirmar: $("setConfirmar").value,
      nome: $("setClinicaNome") ? $("setClinicaNome").value.trim() : "",
      whatsapp: $("setWhatsapp") ? $("setWhatsapp").value.trim() : "",
      email_clinica: $("setClinicaEmail") ? $("setClinicaEmail").value.trim() : "",
      endereco: $("setEndereco") ? $("setEndereco").value.trim() : "",
      horarios: $("setHorarios") ? $("setHorarios").value.trim() : "",
      crefito: $("setCrefito") ? $("setCrefito").value.trim() : ""
    };
    api("PUT", "/api/admin/config", payload)
      .then(function (res) {
        status.textContent = "Dados atualizados.";
        status.className = "form-status is-success";
        if (res.data && res.data.email && $("adminEmail")) $("adminEmail").textContent = res.data.email;
        preencherClinica(res.data || {});
        $("setSenhaAtual").value = "";
        $("setNovaSenha").value = "";
        $("setConfirmar").value = "";
        toast("Configurações salvas.");
      })
      .catch(function (err) {
        status.textContent = err.message;
        status.className = "form-status is-error";
      });
  });

  /* ============================================================
     Agenda
     ============================================================ */

  var WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
  var MONTHS = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
  ];

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function ymd(d) {
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  }

  function parseLocalDt(iso) {
    if (!iso) return null;
    var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]));
  }

  function fmtHora(iso) {
    var d = parseLocalDt(iso);
    if (!d) return "";
    return pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  }

  function toDatetimeLocal(d) {
    return ymd(d) + "T" + pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  }

  function startOfWeek(d) {
    var x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var day = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - day);
    return x;
  }

  function agendaTitle() {
    var d = state.agendaDate;
    if (state.agendaView === "day") {
      return pad2(d.getDate()) + " de " + MONTHS[d.getMonth()] + " de " + d.getFullYear();
    }
    if (state.agendaView === "week") {
      var s = startOfWeek(d);
      var e = new Date(s);
      e.setDate(e.getDate() + 6);
      return pad2(s.getDate()) + "/" + pad2(s.getMonth() + 1) + " – " + pad2(e.getDate()) + "/" + pad2(e.getMonth() + 1) + " de " + e.getFullYear();
    }
    return MONTHS[d.getMonth()] + " de " + d.getFullYear();
  }

  function carregarAgenda() {
    var date = ymd(state.agendaDate);
    document.querySelectorAll("[data-cal-view]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-cal-view") === state.agendaView);
    });
    $("calTitle").textContent = agendaTitle();
    api("GET", "/api/admin/agenda?view=" + encodeURIComponent(state.agendaView) + "&date=" + encodeURIComponent(date))
      .then(function (res) {
        state.agendaItems = (res.data && res.data.items) || [];
        renderAgenda();
      })
      .catch(function (err) {
        toast(err.message, true);
      });
    if (!state.services.length) carregarServicos();
  }

  function eventosDoDia(isoDay) {
    return state.agendaItems.filter(function (it) {
      return String(it.starts_at || "").slice(0, 10) === isoDay;
    });
  }

  function aptChip(it) {
    var cls = APT_STATUS_CLASS[it.status] || "pill--muted";
    return (
      '<button type="button" class="cal-event ' + cls + '" data-apt-id="' + it.id + '">' +
      '<span class="cal-event__time">' + escapeHtml(fmtHora(it.starts_at)) + "</span>" +
      '<span class="cal-event__name">' + escapeHtml(it.patient_name) + "</span>" +
      "</button>"
    );
  }

  function renderAgenda() {
    var body = $("calBody");
    if (!body) return;
    if (state.agendaView === "month") renderMonth(body);
    else if (state.agendaView === "week") renderWeek(body);
    else renderDay(body);

    body.querySelectorAll("[data-apt-id]").forEach(function (el) {
      el.addEventListener("click", function (ev) {
        ev.stopPropagation();
        abrirAgendamento(Number(el.getAttribute("data-apt-id")));
      });
    });
    body.querySelectorAll("[data-cal-day]").forEach(function (el) {
      el.addEventListener("dblclick", function () {
        abrirNovoAgendamento(el.getAttribute("data-cal-day") + "T09:00");
      });
    });
  }

  function renderMonth(body) {
    var d = state.agendaDate;
    var first = new Date(d.getFullYear(), d.getMonth(), 1);
    var start = startOfWeek(first);
    var today = ymd(new Date());
    var html = '<div class="cal-month">';
    html += '<div class="cal-month__head">';
    WEEKDAYS.forEach(function (w) {
      html += "<span>" + w + "</span>";
    });
    html += "</div><div class='cal-month__grid'>";
    for (var i = 0; i < 42; i++) {
      var cell = new Date(start);
      cell.setDate(start.getDate() + i);
      var iso = ymd(cell);
      var outside = cell.getMonth() !== d.getMonth();
      var items = eventosDoDia(iso);
      html +=
        '<div class="cal-cell' +
        (outside ? " is-outside" : "") +
        (iso === today ? " is-today" : "") +
        '" data-cal-day="' +
        iso +
        '">';
      html += '<span class="cal-cell__day">' + cell.getDate() + "</span>";
      html += '<div class="cal-cell__events">';
      items.slice(0, 3).forEach(function (it) {
        html += aptChip(it);
      });
      if (items.length > 3) {
        html += '<span class="cal-cell__more">+' + (items.length - 3) + "</span>";
      }
      html += "</div></div>";
    }
    html += "</div></div>";
    body.innerHTML = html;
  }

  function renderWeek(body) {
    var start = startOfWeek(state.agendaDate);
    var today = ymd(new Date());
    var html = '<div class="cal-week">';
    for (var i = 0; i < 7; i++) {
      var cell = new Date(start);
      cell.setDate(start.getDate() + i);
      var iso = ymd(cell);
      var items = eventosDoDia(iso);
      html +=
        '<div class="cal-week__col' +
        (iso === today ? " is-today" : "") +
        '" data-cal-day="' +
        iso +
        '">';
      html +=
        '<div class="cal-week__head"><strong>' +
        WEEKDAYS[i] +
        "</strong><span>" +
        pad2(cell.getDate()) +
        "/" +
        pad2(cell.getMonth() + 1) +
        "</span></div>";
      html += '<div class="cal-week__events">';
      if (!items.length) html += '<p class="cal-empty">Sem horários</p>';
      items.forEach(function (it) {
        html += aptChip(it);
      });
      html += "</div></div>";
    }
    html += "</div>";
    body.innerHTML = html;
  }

  function renderDay(body) {
    var iso = ymd(state.agendaDate);
    var items = eventosDoDia(iso);
    var html = '<div class="cal-day" data-cal-day="' + iso + '">';
    if (!items.length) {
      html += '<div class="empty-state"><p>Nenhum agendamento neste dia.</p></div>';
    } else {
      html += '<div class="cal-day__list">';
      items.forEach(function (it) {
        html +=
          '<button type="button" class="cal-day__item" data-apt-id="' +
          it.id +
          '">' +
          '<span class="cal-day__time">' +
          escapeHtml(fmtHora(it.starts_at)) +
          (it.ends_at ? " – " + escapeHtml(fmtHora(it.ends_at)) : "") +
          "</span>" +
          '<span class="cal-day__info"><strong>' +
          escapeHtml(it.patient_name) +
          "</strong><small>" +
          escapeHtml(it.service_name || "—") +
          " · " +
          escapeHtml(it.status) +
          "</small></span>" +
          "</button>";
      });
      html += "</div>";
    }
    html += "</div>";
    body.innerHTML = html;
  }

  function shiftAgenda(dir) {
    var d = new Date(state.agendaDate);
    if (state.agendaView === "day") d.setDate(d.getDate() + dir);
    else if (state.agendaView === "week") d.setDate(d.getDate() + 7 * dir);
    else d.setMonth(d.getMonth() + dir);
    state.agendaDate = d;
    carregarAgenda();
  }

  $("btnAgendaPrev").addEventListener("click", function () {
    shiftAgenda(-1);
  });
  $("btnAgendaNext").addEventListener("click", function () {
    shiftAgenda(1);
  });
  $("btnAgendaToday").addEventListener("click", function () {
    state.agendaDate = new Date();
    carregarAgenda();
  });
  document.querySelectorAll("[data-cal-view]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.agendaView = btn.getAttribute("data-cal-view");
      carregarAgenda();
    });
  });

  function preencherServicosAgenda() {
    var sel = $("aptService");
    if (!sel) return;
    var current = sel.value;
    sel.innerHTML = '<option value="">Selecione</option>';
    state.services.forEach(function (s) {
      sel.innerHTML +=
        '<option value="' + s.id + '">' + escapeHtml(s.nome) + "</option>";
    });
    if (current) sel.value = current;
  }

  function abrirNovoAgendamento(startsLocal) {
    $("aptModalTitle").textContent = "Novo agendamento";
    $("aptId").value = "";
    $("aptPatientId").value = "";
    $("aptPatientSearch").value = "";
    $("aptPatientPicked").textContent = "";
    $("aptStarts").value = startsLocal || toDatetimeLocal(new Date());
    $("aptDuration").value = "50";
    $("aptStatus").value = "Agendado";
    $("aptNotes").value = "";
    $("aptFormStatus").textContent = "";
    $("btnDeleteAppointment").hidden = true;
    $("btnAptCreateReg").hidden = true;
    $("aptSuggest").hidden = true;
    preencherServicosAgenda();
    abrirModal("modalAppointment");
    $("aptPatientSearch").focus();
  }

  function abrirAgendamento(id) {
    withServices(function () {
      api("GET", "/api/admin/agenda/" + id)
        .then(function (res) {
          var it = res.data;
          $("aptModalTitle").textContent = "Editar agendamento";
          $("aptId").value = it.id;
          $("aptPatientId").value = it.patient_id || "";
          $("aptPatientSearch").value = it.patient_name || "";
          $("aptPatientPicked").textContent = it.patient_name || "";
          var d = parseLocalDt(it.starts_at);
          $("aptStarts").value = d ? toDatetimeLocal(d) : "";
          $("aptDuration").value = it.duration_min || 50;
          $("aptStatus").value = it.status || "Agendado";
          $("aptNotes").value = it.notes || "";
          $("aptFormStatus").textContent = "";
          $("btnDeleteAppointment").hidden = false;
          $("btnAptCreateReg").hidden = !!it.patient_id;
          $("aptSuggest").hidden = true;
          preencherServicosAgenda();
          if (it.service_id) $("aptService").value = String(it.service_id);
          abrirModal("modalAppointment");
        })
        .catch(function (err) {
          toast(err.message, true);
        });
    });
  }

  function withServices(cb) {
    if (state.services.length) {
      cb();
      return;
    }
    carregarServicos().then(cb);
  }

  $("btnNewAppointment").addEventListener("click", function () {
    withServices(function () {
      abrirNovoAgendamento();
    });
  });

  $("btnAptCreateReg").addEventListener("click", function () {
    var aptId = $("aptId").value;
    var nome = $("aptPatientSearch").value.trim();
    var svcSel = $("aptService");
    if (!nome) {
      toast("Informe o nome do paciente.", true);
      return;
    }
    abrirNovoCadastro({
      nome: nome,
      service_id: svcSel.value,
      servico: svcSel.options[svcSel.selectedIndex] ? svcSel.options[svcSel.selectedIndex].text : "",
      appointment_ids: aptId ? [Number(aptId)] : [],
      observacoes: $("aptNotes").value.trim(),
      status: "Em atendimento"
    });
  });

  $("aptPatientSearch").addEventListener("input", function () {
    var q = $("aptPatientSearch").value.trim();
    $("aptPatientId").value = "";
    clearTimeout(state.aptSuggestTimer);
    if (q.length < 2) {
      $("aptSuggest").hidden = true;
      return;
    }
    state.aptSuggestTimer = setTimeout(function () {
      api("GET", "/api/admin/agenda/pacientes?q=" + encodeURIComponent(q))
        .then(function (res) {
          var list = res.data || [];
          var box = $("aptSuggest");
          if (!list.length) {
            box.innerHTML =
              '<button type="button" class="apt-suggest__item" data-create-reg="1">' +
              "<strong>Nenhum cadastro encontrado</strong>" +
              "<small>Criar ficha para " +
              escapeHtml(q) +
              "</small></button>";
            box.hidden = false;
            box.querySelector("[data-create-reg]").addEventListener("click", function () {
              box.hidden = true;
              abrirNovoCadastro({
                nome: q,
                status: "Em atendimento"
              });
            });
            return;
          }
          box.innerHTML = list
            .map(function (p) {
              return (
                '<button type="button" class="apt-suggest__item" data-pid="' +
                p.id +
                '" data-pname="' +
                escapeHtml(p.nome) +
                '" data-pservico="' +
                escapeHtml(p.servico || "") +
                '">' +
                "<strong>" +
                escapeHtml(p.nome) +
                "</strong><small>" +
                escapeHtml(p.telefone || "") +
                " · " +
                escapeHtml(p.servico || "") +
                "</small></button>"
              );
            })
            .join("");
          box.hidden = false;
          box.querySelectorAll("[data-pid]").forEach(function (btn) {
            btn.addEventListener("click", function () {
              $("aptPatientId").value = btn.getAttribute("data-pid");
              $("aptPatientSearch").value = btn.getAttribute("data-pname");
              $("aptPatientPicked").textContent = btn.getAttribute("data-pname");
              box.hidden = true;
              var servicoNome = btn.getAttribute("data-pservico");
              if (servicoNome) {
                var match = state.services.find(function (s) {
                  return s.nome === servicoNome;
                });
                if (match) $("aptService").value = String(match.id);
              }
            });
          });
        })
        .catch(function () {});
    }, 220);
  });

  $("appointmentForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var status = $("aptFormStatus");
    status.textContent = "";
    var nome = $("aptPatientSearch").value.trim();
    var starts = $("aptStarts").value;
    if (!nome) {
      status.textContent = "Informe o paciente.";
      status.className = "form-status is-error";
      return;
    }
    if (!starts) {
      status.textContent = "Informe data e horário.";
      status.className = "form-status is-error";
      return;
    }
    var svcSel = $("aptService");
    var payload = {
      patient_id: $("aptPatientId").value ? Number($("aptPatientId").value) : null,
      patient_name: nome,
      starts_at: starts,
      duration_min: Number($("aptDuration").value) || 50,
      service_id: svcSel.value ? Number(svcSel.value) : null,
      service_name: svcSel.options[svcSel.selectedIndex] ? svcSel.options[svcSel.selectedIndex].text : "",
      status: $("aptStatus").value,
      notes: $("aptNotes").value
    };
    var id = $("aptId").value;
    var req = id
      ? api("PUT", "/api/admin/agenda/" + id, payload)
      : api("POST", "/api/admin/agenda", payload);
    req
      .then(function () {
        fecharModal("modalAppointment");
        toast(id ? "Agendamento atualizado." : "Agendamento criado.");
        carregarAgenda();
      })
      .catch(function (err) {
        status.textContent = err.message;
        status.className = "form-status is-error";
      });
  });

  var recordKind = "";

  function fieldHtml(id, label, type, extra) {
    extra = extra || "";
    if (type === "textarea") {
      return '<div class="field"><label class="field__label" for="' + id + '">' + label + '</label><textarea class="input input--textarea" id="' + id + '" rows="3" ' + extra + "></textarea></div>";
    }
    return '<div class="field"><label class="field__label" for="' + id + '">' + label + '</label><input class="input" type="' + (type || "text") + '" id="' + id + '" ' + extra + "></div>";
  }

  function openRecord(kind, title, html) {
    recordKind = kind;
    $("recordTitle").textContent = title;
    $("recordFields").innerHTML = html;
    $("recordStatus").textContent = "";
    abrirModal("modalRecord");
  }

  function fillTable(bodyId, emptyId, rows, cols, delUrl) {
    var body = $(bodyId);
    var empty = $(emptyId);
    if (!body) return;
    if (!rows.length) {
      body.innerHTML = "";
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    body.innerHTML = rows
      .map(function (r) {
        return (
          "<tr>" +
          cols(r) +
          '<td class="th-actions"><button class="btn btn--danger btn--sm" type="button" data-del="' +
          r.id +
          '">Excluir</button></td></tr>'
        );
      })
      .join("");
    body.querySelectorAll("[data-del]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        confirmar("Excluir registro", "Esta ação não pode ser desfeita.", function () {
          api("DELETE", delUrl + btn.getAttribute("data-del"))
            .then(function () {
              toast("Registro excluído.");
              aplicarView(state.view);
            })
            .catch(function (err) {
              toast(err.message, true);
            });
        });
      });
    });
  }

  function carregarAvaliacoes() {
    api("GET", "/api/admin/evaluations").then(function (res) {
      fillTable("evalTableBody", "evalEmpty", res.data || [], function (r) {
        return "<td>" + escapeHtml(r.patient_name) + "</td><td>" + escapeHtml(fmtData(r.evaluated_at)) + "</td><td class='hide-sm'>" + escapeHtml(r.queixa) + "</td>";
      }, "/api/admin/evaluations/");
    }).catch(function (err) { toast(err.message, true); });
  }
  function carregarEvolucoes() {
    api("GET", "/api/admin/evolutions").then(function (res) {
      fillTable("evoTableBody", "evoEmpty", res.data || [], function (r) {
        return "<td>" + escapeHtml(r.patient_name) + "</td><td>" + escapeHtml(fmtData(r.evolution_date)) + "</td><td class='hide-sm'>" + escapeHtml(r.procedimentos) + "</td>";
      }, "/api/admin/evolutions/");
    }).catch(function (err) { toast(err.message, true); });
  }
  function carregarExercicios() {
    api("GET", "/api/admin/exercises").then(function (res) {
      fillTable("exTableBody", "exEmpty", res.data || [], function (r) {
        return "<td>" + escapeHtml(r.nome) + "</td><td class='hide-sm'>" + escapeHtml(r.categoria) + "</td><td class='hide-sm'>" + escapeHtml(r.regiao) + "</td>";
      }, "/api/admin/exercises/");
    }).catch(function (err) { toast(err.message, true); });
  }
  function payQuery() {
    var params = [];
    if (state.payPeriodo) params.push("periodo=" + encodeURIComponent(state.payPeriodo));
    if ($("payDe") && $("payDe").value) params.push("de=" + encodeURIComponent($("payDe").value));
    if ($("payAte") && $("payAte").value) params.push("ate=" + encodeURIComponent($("payAte").value));
    if ($("payPaciente") && $("payPaciente").value.trim()) params.push("q=" + encodeURIComponent($("payPaciente").value.trim()));
    if ($("payServico") && $("payServico").value) params.push("servico=" + encodeURIComponent($("payServico").value));
    if ($("payForma") && $("payForma").value) params.push("method=" + encodeURIComponent($("payForma").value));
    if ($("payStatus") && $("payStatus").value) params.push("status=" + encodeURIComponent($("payStatus").value));
    return params.length ? "?" + params.join("&") : "";
  }

  function preencherFiltroPayServicos() {
    var sel = $("payServico");
    if (!sel) return;
    var atual = sel.value;
    sel.innerHTML = '<option value="">Todos os serviços</option>';
    state.services.forEach(function (s) {
      sel.innerHTML += '<option value="' + escapeHtml(s.nome) + '">' + escapeHtml(s.nome) + "</option>";
    });
    sel.value = atual;
  }

  function carregarFinanceiro() {
    if (!state.services.length) carregarServicos().then(preencherFiltroPayServicos);
    else preencherFiltroPayServicos();
    api("GET", "/api/admin/payments" + payQuery()).then(function (res) {
      var rows = res.data || [];
      var s = res.resumo || {};
      if ($("payRecebido")) $("payRecebido").textContent = moeda(s.recebido);
      if ($("payPendente")) $("payPendente").textContent = moeda(s.pendente);
      if ($("payCancelado")) $("payCancelado").textContent = moeda(s.cancelado);
      if ($("payPix")) $("payPix").textContent = moeda(s.pix);
      if ($("payDinheiro")) $("payDinheiro").textContent = moeda(s.dinheiro);
      var body = $("payTableBody");
      var empty = $("payEmpty");
      if (!rows.length) {
        if (body) body.innerHTML = "";
        if (empty) empty.hidden = false;
        return;
      }
      if (empty) empty.hidden = true;
      body.innerHTML = rows
        .map(function (r) {
          var acoes = "";
          if (r.status === "Pendente") {
            acoes =
              '<button class="btn btn--outline btn--sm" type="button" data-pay-status="Pago" data-id="' + r.id + '">Pago</button>' +
              '<button class="btn btn--danger btn--sm" type="button" data-pay-status="Cancelado" data-id="' + r.id + '">Cancelar</button>';
          } else {
            acoes = '<span class="cell-muted">—</span>';
          }
          return (
            "<tr>" +
            "<td>" + escapeHtml(r.patient_name) + "</td>" +
            "<td>" + escapeHtml(r.service_name || "—") + "</td>" +
            "<td>" + moeda(r.amount) + "</td>" +
            "<td>" + escapeHtml(r.method || "—") + "</td>" +
            "<td>" + pill(r.status) + "</td>" +
            '<td class="hide-sm">' + escapeHtml(fmtData(r.criadoEm)) + "</td>" +
            '<td class="th-actions"><div class="row-actions">' + acoes + "</div></td></tr>"
          );
        })
        .join("");
    }).catch(function (err) { toast(err.message, true); });
  }
  function carregarDocumentos() {
    api("GET", "/api/admin/documents").then(function (res) {
      fillTable("docTableBody", "docEmpty", res.data || [], function (r) {
        return "<td>" + escapeHtml(r.titulo) + "</td><td>" + escapeHtml(r.patient_name) + "</td><td class='hide-sm'>" + escapeHtml(r.tipo) + "</td>";
      }, "/api/admin/documents/");
    }).catch(function (err) { toast(err.message, true); });
  }
  function carregarUsuarios() {
    api("GET", "/api/admin/users").then(function (res) {
      var body = $("usersTableBody");
      if (!body) return;
      body.innerHTML = (res.data || [])
        .map(function (u) {
          return "<tr><td>" + escapeHtml(u.nome || "—") + "</td><td>" + escapeHtml(u.email) + "</td><td>" + escapeHtml(u.role || "") + "</td></tr>";
        })
        .join("");
    }).catch(function (err) { toast(err.message, true); });
  }
  function relatorioQuery() {
    var params = [];
    if ($("repDe") && $("repDe").value) params.push("de=" + encodeURIComponent($("repDe").value));
    if ($("repAte") && $("repAte").value) params.push("ate=" + encodeURIComponent($("repAte").value));
    return params.length ? "?" + params.join("&") : "";
  }

  function cardStat(label, value) {
    return '<article class="stat-card"><span class="stat-card__label">' + label + '</span><span class="stat-card__value">' + value + "</span></article>";
  }

  function carregarRelatorios() {
    var q = relatorioQuery();
    if ($("btnRepPdf")) $("btnRepPdf").href = "/api/admin/payments/relatorio" + q;
    api("GET", "/api/admin/relatorios" + q).then(function (res) {
      var data = res.data || {};
      var p = data.pacientes || {};
      var a = data.atendimentos || {};
      var d = data.financeiro || {};
      var pacEl = $("reportsPacientes");
      if (pacEl) {
        pacEl.innerHTML =
          cardStat("Pacientes totais", p.total || 0) +
          cardStat("Pacientes ativos", p.ativos || 0) +
          cardStat("Novos no período", p.novos || 0) +
          cardStat("Lista de espera", p.lista_espera || 0);
      }
      var agEl = $("reportsAgenda");
      if (agEl) {
        agEl.innerHTML =
          cardStat("Atendimentos", a.total || 0) +
          cardStat("Realizados", a.realizados || 0) +
          cardStat("Faltas", a.faltas || 0) +
          cardStat("Cancelamentos", a.cancelamentos || 0) +
          cardStat("Ocupação", (a.ocupacao || 0) + "%") +
          cardStat("Evoluções", data.evolucoes || 0);
      }
      var el = $("reportsStats");
      if (el) {
        el.innerHTML =
          cardStat("Total faturado", moeda(d.faturado)) +
          cardStat("Total recebido", moeda(d.recebido)) +
          cardStat("Total pendente", moeda(d.pendente)) +
          cardStat("Total cancelado", moeda(d.cancelado)) +
          cardStat("Recebido via Pix", moeda(d.recebido_pix)) +
          cardStat("Recebido em dinheiro", moeda(d.recebido_dinheiro));
      }
      var rows = data.lancamentos || [];
      var body = $("repTableBody");
      var empty = $("repEmpty");
      if (!body) return;
      if (!rows.length) {
        body.innerHTML = "";
        if (empty) empty.hidden = false;
        return;
      }
      if (empty) empty.hidden = true;
      body.innerHTML = rows
        .map(function (r) {
          return (
            "<tr><td>" + escapeHtml(r.patient_name) + "</td><td>" + escapeHtml(r.service_name || "—") +
            "</td><td>" + moeda(r.amount) + "</td><td>" + escapeHtml(r.method || "—") +
            "</td><td>" + pill(r.status) + '</td><td class="hide-sm">' + escapeHtml(fmtData(r.criadoEm)) + "</td></tr>"
          );
        })
        .join("");
    }).catch(function (err) { toast(err.message, true); });
  }

  if ($("btnNewEval")) $("btnNewEval").addEventListener("click", function () {
    openRecord("eval", "Nova avaliação", fieldHtml("rNome", "Paciente") + fieldHtml("rData", "Data", "date") + fieldHtml("rQueixa", "Queixa principal", "textarea") + fieldHtml("rObj", "Objetivos", "textarea") + fieldHtml("rHist", "Histórico", "textarea") + fieldHtml("rFunc", "Avaliação funcional", "textarea") + fieldHtml("rPlano", "Plano terapêutico", "textarea"));
  });
  if ($("btnNewEvo")) $("btnNewEvo").addEventListener("click", function () {
    openRecord("evo", "Nova evolução", fieldHtml("rNome", "Paciente") + fieldHtml("rData", "Data", "date") + fieldHtml("rProc", "Procedimentos", "textarea") + fieldHtml("rEx", "Exercícios", "textarea") + fieldHtml("rResp", "Resposta do paciente", "textarea") + fieldHtml("rCond", "Próxima conduta", "textarea"));
  });
  if ($("btnNewEx")) $("btnNewEx").addEventListener("click", function () {
    openRecord("ex", "Novo exercício", fieldHtml("rNome", "Nome") + fieldHtml("rCat", "Categoria") + fieldHtml("rReg", "Região") + fieldHtml("rObj", "Objetivo") + fieldHtml("rDesc", "Descrição", "textarea") + fieldHtml("rInst", "Instruções", "textarea"));
  });
  document.querySelectorAll("[data-pay-periodo]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      state.payPeriodo = btn.getAttribute("data-pay-periodo") || "";
      document.querySelectorAll("[data-pay-periodo]").forEach(function (b) {
        b.classList.toggle("is-active", b === btn);
      });
      if (state.payPeriodo && $("payDe")) $("payDe").value = "";
      if (state.payPeriodo && $("payAte")) $("payAte").value = "";
      carregarFinanceiro();
    });
  });
  ["payDe", "payAte", "payPaciente", "payServico", "payForma", "payStatus"].forEach(function (id) {
    var el = $(id);
    if (!el) return;
    el.addEventListener(el.tagName === "SELECT" || el.type === "date" ? "change" : "input", function () {
      if ((id === "payDe" || id === "payAte") && (el.value || ($("payDe") && $("payDe").value) || ($("payAte") && $("payAte").value))) {
        state.payPeriodo = "";
        document.querySelectorAll("[data-pay-periodo]").forEach(function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-pay-periodo") === "");
        });
      }
      carregarFinanceiro();
    });
  });
  if ($("payTableBody")) {
    $("payTableBody").addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-pay-status]");
      if (!btn) return;
      api("PUT", "/api/admin/payments/" + btn.getAttribute("data-id"), { status: btn.getAttribute("data-pay-status") })
        .then(function () {
          toast("Lançamento atualizado.");
          carregarFinanceiro();
        })
        .catch(function (err) {
          toast(err.message, true);
        });
    });
  }
  if ($("btnRepAtualizar")) $("btnRepAtualizar").addEventListener("click", carregarRelatorios);
  ["repDe", "repAte"].forEach(function (id) {
    var el = $(id);
    if (el) el.addEventListener("change", carregarRelatorios);
  });

  if ($("btnNewPay")) $("btnNewPay").addEventListener("click", function () {
    openRecord(
      "pay",
      "Registrar pagamento",
      fieldHtml("rNome", "Paciente") +
        fieldHtml("rServico", "Serviço") +
        fieldHtml("rVal", "Valor (R$)", "number") +
        '<div class="field"><label class="field__label" for="rMethod">Forma de pagamento</label><select class="input" id="rMethod"><option>Pix</option><option>Dinheiro</option></select></div>' +
        '<div class="field"><label class="field__label" for="rStatus">Status</label><select class="input" id="rStatus"><option>Pendente</option><option>Pago</option><option>Cancelado</option></select></div>' +
        fieldHtml("rNotes", "Observações", "textarea")
    );
  });
  if ($("btnNewDoc")) $("btnNewDoc").addEventListener("click", function () {
    openRecord("doc", "Novo documento", fieldHtml("rTitulo", "Título") + fieldHtml("rNome", "Paciente") + fieldHtml("rTipo", "Tipo") + fieldHtml("rNotes", "Observações", "textarea"));
  });

  if ($("recordForm")) {
    $("recordForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var payload = {};
      var url = "";
      if (recordKind === "eval") {
        url = "/api/admin/evaluations";
        payload = { patient_name: $("rNome").value, evaluated_at: $("rData").value, queixa: $("rQueixa").value, objetivos: $("rObj").value, historico: $("rHist").value, avaliacao_funcional: $("rFunc").value, plano: $("rPlano").value };
      } else if (recordKind === "evo") {
        url = "/api/admin/evolutions";
        payload = { patient_name: $("rNome").value, evolution_date: $("rData").value, procedimentos: $("rProc").value, exercicios: $("rEx").value, resposta: $("rResp").value, proxima_conduta: $("rCond").value };
      } else if (recordKind === "ex") {
        url = "/api/admin/exercises";
        payload = { nome: $("rNome").value, categoria: $("rCat").value, regiao: $("rReg").value, objetivo: $("rObj").value, descricao: $("rDesc").value, instrucoes: $("rInst").value };
      } else if (recordKind === "pay") {
        url = "/api/admin/payments";
        payload = { patient_name: $("rNome").value, service_name: $("rServico") ? $("rServico").value : "", amount: $("rVal").value, method: $("rMethod") ? $("rMethod").value : "", status: $("rStatus").value, notes: $("rNotes").value };
      } else if (recordKind === "doc") {
        url = "/api/admin/documents";
        payload = { titulo: $("rTitulo").value, patient_name: $("rNome").value, tipo: $("rTipo").value, notes: $("rNotes").value };
      }
      api("POST", url, payload)
        .then(function () {
          fecharModal("modalRecord");
          toast("Registro salvo.");
          aplicarView(state.view);
        })
        .catch(function (err) {
          $("recordStatus").textContent = err.message;
          $("recordStatus").className = "form-status is-error";
        });
    });
  }

  $("btnDeleteAppointment").addEventListener("click", function () {
    var id = $("aptId").value;
    if (!id) return;
    confirmar("Excluir agendamento", "Este horário será removido da agenda.", function () {
      api("DELETE", "/api/admin/agenda/" + id)
        .then(function () {
          fecharModal("modalAppointment");
          toast("Agendamento excluído.");
          carregarAgenda();
        })
        .catch(function (err) {
          toast(err.message, true);
        });
    });
  });

  /* ============================================================
     Badges / logout / boot
     ============================================================ */

  function actualizarBadges() {
    var bC = $("badgeCadastros");
    var bW = $("badgeWaitlist");
    api("GET", "/api/admin/overview").then(function (res) {
      var d = res.data || {};
      if (d.total_cadastros) {
        bC.textContent = d.total_cadastros;
        bC.hidden = false;
      } else {
        bC.hidden = true;
      }
      if (d.lista_espera) {
        bW.textContent = d.lista_espera;
        bW.hidden = false;
      } else {
        bW.hidden = true;
      }
    }).catch(function () {});
  }

  document.querySelectorAll("[data-logout]").forEach(function (link) {
    link.addEventListener("click", function (ev) {
      ev.preventDefault();
      api("POST", "/api/admin/logout", {})
        .catch(function () {})
        .then(function () {
          window.location.replace("/admin-login");
        });
    });
  });

  function boot() {
    var now = new Date();
    if ($("topbarDate")) {
      $("topbarDate").textContent =
        pad2(now.getDate()) + " " + MONTHS[now.getMonth()].slice(0, 3) + " " + now.getFullYear();
    }
    api("GET", "/api/admin/me")
      .then(function (res) {
        state.waitlist = [];
        aplicarView(rotaAtual());
        actualizarBadges();
      })
      .catch(function () {
        window.location.replace("/admin-login");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
