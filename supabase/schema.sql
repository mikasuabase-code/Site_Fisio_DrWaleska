-- ============================================================================
-- Dra. Waleska Paula — Plataforma de Gestão Clínica
-- Schema PostgreSQL para Supabase
--
-- Como usar:
--   1. Abra o projeto no Supabase > SQL Editor
--   2. Cole TODO o conteudo deste arquivo e execute (Run)
--
-- Seguranca:
--   - RLS habilitado em TODAS as tabelas.
--   - Nenhuma policy para "anon"/"authenticated": o frontend NAO acessa o banco
--     diretamente. Todo acesso passa pelo backend Flask usando a service_role key,
--     que fica apenas em variavel de ambiente no servidor.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ============================================================================
-- 1. USUARIOS DA EQUIPE (acesso ao painel)
-- ============================================================================
create table if not exists staff_users (
  id             uuid primary key default gen_random_uuid(),
  email          text not null unique,
  password_hash  text not null,
  full_name      text not null default '',
  role           text not null default 'admin' check (role in ('admin', 'profissional', 'recepcao')),
  active         boolean not null default true,
  last_login_at  timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- ============================================================================
-- 2. SERVICOS E VALORES (alimentam o site publico)
-- ============================================================================
create table if not exists services (
  id                uuid primary key default gen_random_uuid(),
  name              text not null,
  description       text not null default '',
  price             numeric(10,2) not null default 0,
  duration_min      integer not null default 50 check (duration_min > 0),
  extra_info        text not null default '',
  icon              text not null default 'padrao',
  requires_waitlist boolean not null default false,
  active            boolean not null default true,
  sort_order        integer not null default 0,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ============================================================================
-- 3. PACIENTES (cadastro unico e historico unico)
-- ============================================================================
create table if not exists patients (
  id             uuid primary key default gen_random_uuid(),
  full_name      text not null,
  birth_date     date,
  phone          text not null,
  whatsapp       text,
  email          text,
  service_id     uuid references services(id) on delete set null,
  start_date     date,
  goal           text not null default '',
  main_complaint text not null default '',
  limitations    text not null default '',
  notes          text not null default '',
  status         text not null default 'Novo',
  active         boolean not null default true,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists idx_patients_service on patients(service_id);
create index if not exists idx_patients_status  on patients(status);
create index if not exists idx_patients_name    on patients(full_name);

-- ============================================================================
-- 4. AVALIACAO INICIAL (prontuario)
-- ============================================================================
create table if not exists evaluations (
  id               uuid primary key default gen_random_uuid(),
  patient_id       uuid not null references patients(id) on delete cascade,
  professional_id  uuid references staff_users(id) on delete set null,
  evaluated_at     date not null default current_date,
  main_complaint   text not null default '',
  clinical_history text not null default '',
  physical_exam    text not null default '',
  diagnosis        text not null default '',
  goals            text not null default '',
  notes            text not null default '',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_evaluations_patient on evaluations(patient_id);

-- ============================================================================
-- 5. DUPLAS DE PILATES
-- ============================================================================
create table if not exists duplas (
  id          uuid primary key default gen_random_uuid(),
  name        text not null default '',
  service_id  uuid references services(id) on delete set null,
  status      text not null default 'Em dupla'
              check (status in ('Em dupla', 'Em atendimento', 'Finalizado', 'Desfeita')),
  notes       text not null default '',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists dupla_members (
  id          uuid primary key default gen_random_uuid(),
  dupla_id    uuid not null references duplas(id) on delete cascade,
  patient_id  uuid not null references patients(id) on delete cascade,
  joined_at   timestamptz not null default now(),
  active      boolean not null default true,
  unique (dupla_id, patient_id)
);

create index if not exists idx_dupla_members_dupla   on dupla_members(dupla_id);
create index if not exists idx_dupla_members_patient on dupla_members(patient_id);

-- ============================================================================
-- 6. AGENDAMENTOS / ATENDIMENTOS (agenda)
-- ============================================================================
create table if not exists appointments (
  id                uuid primary key default gen_random_uuid(),
  patient_id        uuid not null references patients(id) on delete cascade,
  service_id        uuid references services(id) on delete set null,
  dupla_id          uuid references duplas(id) on delete set null,
  pilates_class_id  uuid,
  starts_at         timestamptz not null,
  ends_at           timestamptz,
  duration_min      integer not null default 50,
  status            text not null default 'Agendado'
                    check (status in ('Agendado', 'Confirmado', 'Realizado', 'Cancelado', 'Faltou', 'Reagendado')),
  notes             text not null default '',
  created_by        uuid references staff_users(id) on delete set null,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_appointments_patient on appointments(patient_id);
create index if not exists idx_appointments_start   on appointments(starts_at);
create index if not exists idx_appointments_status  on appointments(status);
create index if not exists idx_appointments_dupla   on appointments(dupla_id);

-- ============================================================================
-- 7. AULAS DE PILATES (turmas recorrentes)
-- ============================================================================
create table if not exists pilates_classes (
  id            uuid primary key default gen_random_uuid(),
  dupla_id      uuid references duplas(id) on delete set null,
  service_id    uuid references services(id) on delete set null,
  title         text not null default '',
  weekday       smallint check (weekday between 0 and 6),
  start_time    time not null,
  duration_min  integer not null default 50,
  location      text not null default '',
  status        text not null default 'Ativa'
                check (status in ('Ativa', 'Suspensa', 'Encerrada')),
  notes         text not null default '',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

alter table appointments
  drop constraint if exists appointments_pilates_class_id_fkey;
alter table appointments
  add constraint appointments_pilates_class_id_fkey
  foreign key (pilates_class_id) references pilates_classes(id) on delete set null;

create table if not exists class_participants (
  id          uuid primary key default gen_random_uuid(),
  class_id    uuid not null references pilates_classes(id) on delete cascade,
  patient_id  uuid not null references patients(id) on delete cascade,
  active      boolean not null default true,
  unique (class_id, patient_id)
);

create index if not exists idx_class_participants_class   on class_participants(class_id);
create index if not exists idx_class_participants_patient on class_participants(patient_id);

-- ============================================================================
-- 8. PRESENCA (por atendimento e por participante)
-- ============================================================================
create table if not exists attendance (
  id              uuid primary key default gen_random_uuid(),
  appointment_id  uuid not null references appointments(id) on delete cascade,
  patient_id      uuid not null references patients(id) on delete cascade,
  status          text not null default 'Confirmado'
                  check (status in ('Confirmado', 'Realizado', 'Cancelado', 'Faltou')),
  checked_at      timestamptz not null default now(),
  notes           text not null default '',
  unique (appointment_id, patient_id)
);

create index if not exists idx_attendance_appointment on attendance(appointment_id);
create index if not exists idx_attendance_patient     on attendance(patient_id);

-- ============================================================================
-- 9. EVOLUCOES (registro clinico por atendimento)
-- ============================================================================
create table if not exists evolutions (
  id                uuid primary key default gen_random_uuid(),
  patient_id        uuid not null references patients(id) on delete cascade,
  appointment_id    uuid references appointments(id) on delete set null,
  professional_id   uuid references staff_users(id) on delete set null,
  evolution_date    date not null default current_date,
  complaint         text not null default '',
  procedures        text not null default '',
  exercises         text not null default '',
  observed_evolution text not null default '',
  patient_response  text not null default '',
  notes             text not null default '',
  guidance          text not null default '',
  next_steps        text not null default '',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_evolutions_patient     on evolutions(patient_id);
create index if not exists idx_evolutions_appointment on evolutions(appointment_id);
create index if not exists idx_evolutions_date        on evolutions(evolution_date);

-- ============================================================================
-- 10. LISTA DE ESPERA DO PILATES
-- ============================================================================
create table if not exists waitlist (
  id              uuid primary key default gen_random_uuid(),
  patient_id      uuid not null references patients(id) on delete cascade,
  service_id      uuid references services(id) on delete set null,
  age             integer,
  difficulties    text not null default '',
  available_days  jsonb not null default '[]'::jsonb,
  available_times jsonb not null default '[]'::jsonb,
  priority        integer not null default 0,
  status          text not null default 'Lista de espera'
                  check (status in ('Lista de espera', 'Aguardando dupla', 'Em atendimento', 'Finalizado', 'Desistiu')),
  notes           text not null default '',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists idx_waitlist_status  on waitlist(status);
create index if not exists idx_waitlist_patient on waitlist(patient_id);

-- ============================================================================
-- 11. ARQUIVOS (documentos, exames, PDFs)
-- ============================================================================
create table if not exists files (
  id            uuid primary key default gen_random_uuid(),
  patient_id    uuid references patients(id) on delete cascade,
  evolution_id  uuid references evolutions(id) on delete set null,
  file_name     text not null,
  storage_path  text not null,
  mime_type     text not null default '',
  size_bytes    bigint not null default 0,
  uploaded_by   uuid references staff_users(id) on delete set null,
  created_at    timestamptz not null default now()
);

create index if not exists idx_files_patient on files(patient_id);

-- ============================================================================
-- 12. RELATORIOS GERADOS
-- ============================================================================
create table if not exists reports (
  id             uuid primary key default gen_random_uuid(),
  patient_id     uuid references patients(id) on delete set null,
  service_id     uuid references services(id) on delete set null,
  period_start   date,
  period_end     date,
  kind           text not null default 'individual'
                 check (kind in ('individual', 'administrativo')),
  payload        jsonb not null default '{}'::jsonb,
  pdf_path       text,
  generated_by   uuid references staff_users(id) on delete set null,
  generated_at   timestamptz not null default now()
);

create index if not exists idx_reports_patient on reports(patient_id);

-- ============================================================================
-- 13. CONFIGURACOES (chave/valor)
-- ============================================================================
create table if not exists settings (
  key         text primary key,
  value       jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

-- ============================================================================
-- 14. TRIGGER updated_at
-- ============================================================================
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

do $$
declare
  t text;
begin
  foreach t in array array[
    'staff_users', 'services', 'patients', 'evaluations', 'duplas',
    'appointments', 'pilates_classes', 'evolutions', 'waitlist'
  ]
  loop
    execute format('drop trigger if exists trg_%1$s_updated_at on %1$s', t);
    execute format(
      'create trigger trg_%1$s_updated_at before update on %1$s
       for each row execute function set_updated_at()', t
    );
  end loop;
end;
$$;

-- ============================================================================
-- 15. ROW LEVEL SECURITY
-- RLS habilitado + SEM policies publicas.
-- O backend Flask usa a service_role key (server-side), que ignora RLS.
-- Resultado: o frontend nao consegue ler nem escrever nada diretamente.
-- ============================================================================
alter table staff_users      enable row level security;
alter table services         enable row level security;
alter table patients         enable row level security;
alter table evaluations      enable row level security;
alter table duplas           enable row level security;
alter table dupla_members    enable row level security;
alter table appointments     enable row level security;
alter table pilates_classes  enable row level security;
alter table class_participants enable row level security;
alter table attendance       enable row level security;
alter table evolutions       enable row level security;
alter table waitlist         enable row level security;
alter table files            enable row level security;
alter table reports          enable row level security;
alter table settings         enable row level security;

-- Revoga acesso direto dos papeis publicos (defesa em profundidade)
revoke all on all tables in schema public from anon;
revoke all on all tables in schema public from authenticated;
revoke all on all sequences in schema public from anon;
revoke all on all sequences in schema public from authenticated;

-- ============================================================================
-- 16. SEED INICIAL (servicos e configuracoes do formulario)
-- ============================================================================
insert into services (name, description, price, duration_min, extra_info, icon, requires_waitlist, active, sort_order)
values
  ('Pilates Clínico',
   'Exercícios individualizados que fortalecem o corpo com segurança, respeitando limitações e histórico de cada pessoa.',
   90.00, 50, 'Sessões de 50 minutos. Pacote mensal com condições especiais.', 'pilates', true, true, 1),
  ('Fisioterapia Ortopédica',
   'Tratamento de dores e lesões musculoesqueléticas com técnicas manuais e exercícios terapêuticos.',
   120.00, 50, 'Avaliação inicial incluída na primeira sessão.', 'ortopedica', false, true, 2),
  ('RPG — Reeducação Postural Global',
   'Reeducação postural global para corrigir desequilíbrios e aliviar dores crônicas.',
   140.00, 60, 'Sessões individuais com alongamentos posturais específicos.', 'rpg', false, true, 3),
  ('Liberação Miofascial',
   'Técnica manual para liberar tensões musculares e melhorar a mobilidade dos tecidos.',
   100.00, 50, 'Indicada para dores musculares e restrições de movimento.', 'miofascial', false, true, 4),
  ('Pilates para Gestantes',
   'Acompanhamento especializado para manter o corpo forte e preparado durante a gestação.',
   90.00, 50, 'Aulas adaptadas a cada fase da gestação, com liberação do obstetra.', 'gestantes', true, true, 5),
  ('Fisioterapia Esportiva',
   'Prevenção e recuperação de lesões para quem pratica atividades físicas e esportes.',
   120.00, 50, 'Atendimento voltado a atletas e praticantes de atividades físicas.', 'esportiva', false, true, 6)
on conflict do nothing;

insert into settings (key, value) values
  ('cadastro_dias', '["Segunda","Terça","Quarta","Quinta","Sexta","Sábado"]'::jsonb),
  ('cadastro_frequencias', '["1x por semana","2x por semana","3x por semana","Mais de 3x por semana"]'::jsonb),
  ('cadastro_motivos', '["Fortalecer o corpo","Melhorar a postura","Aliviar dores","Ganhar flexibilidade","Cuidar da mente","Reabilitação"]'::jsonb),
  ('clinica', '{"nome":"Dra. Waleska Paula","cidades":"João Pessoa / Caaporã","duracao_aula":50,"compatibilidade_minima":60}'::jsonb)
on conflict (key) do nothing;
