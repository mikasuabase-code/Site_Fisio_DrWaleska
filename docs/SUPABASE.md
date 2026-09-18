# Configurar o Supabase

Guia passo a passo para ligar a plataforma ao Supabase. O código já está preparado:
você só precisa criar o projeto e preencher o arquivo `.env`.

## Visão geral

- **O frontend nunca fala com o Supabase.** Toda leitura e escrita passa pelo
  backend Flask, que guarda a chave secreta em variável de ambiente.
- **RLS ativado em todas as tabelas**, sem nenhuma policy pública. Ninguém
  consegue acessar os dados clínicos diretamente pela internet.
- Enquanto você não configurar o Supabase, a plataforma continua funcionando com
  o banco local SQLite (`DB_BACKEND=sqlite`).

## 1. Criar o projeto

1. Acesse https://supabase.com e crie uma conta (ou entre).
2. Clique em **New project**.
3. Preencha:
   - **Name**: `site-fisio-drwaleska`
   - **Database Password**: crie uma senha forte e guarde
   - **Region**: `South America (São Paulo)` (mais próximo do Brasil)
4. Clique em **Create new project** e aguarde alguns minutos.

## 2. Executar o schema

1. No projeto, abra **SQL Editor** (menu lateral) → **New query**.
2. Abra o arquivo `supabase/schema.sql` deste repositório.
3. Copie **todo** o conteúdo, cole no editor e clique em **Run**.
4. Confirme em **Table Editor** que as tabelas foram criadas:
   `staff_users`, `services`, `patients`, `evaluations`, `duplas`,
   `dupla_members`, `appointments`, `pilates_classes`, `class_participants`,
   `attendance`, `evolutions`, `waitlist`, `files`, `reports`, `settings`.

O schema já insere os 6 serviços e as opções do formulário de cadastro.

## 3. Copiar as credenciais

1. No Supabase, abra **Project Settings** (engrenagem) → **API**.
2. Copie:
   - **Project URL** → vai para `SUPABASE_URL`
   - **service_role** (em *Project API keys*, clique em *Reveal*) →
     vai para `SUPABASE_SERVICE_ROLE_KEY`
3. No terminal deste projeto:
   ```bash
   cp .env.example .env
   ```
4. Edite o `.env` e preencha `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`.
5. Troque `DB_BACKEND=sqlite` por:
   ```
   DB_BACKEND=supabase
   ```

## 4. Segurança — regras que não podem ser quebradas

- A chave `service_role` **ignora o RLS**. Ela é a chave-mestra do banco.
  - Fica **somente** no `.env` do servidor.
  - Nunca commitar no Git, nunca colar no chat, nunca colocar no HTML/JS.
- O arquivo `.env` já está no `.gitignore`. Confirme antes de qualquer commit.
- Se a chave vazar, rotacione imediatamente em
  **Project Settings → API → Rotate service_role key**.

## 5. Verificação

Com `DB_BACKEND=supabase` e o servidor rodando:

```bash
curl -s http://localhost:8000/api/services
```

Deve retornar os serviços vindos do Supabase. Depois acesse `/admin-login`,
entre e confirme que os dados aparecem no painel.

## 6. Como funciona o RLS aqui

| Papel | Acesso ao banco |
|---|---|
| `anon` (frontend público) | **nenhum** — revogado |
| `authenticated` | **nenhum** — revogado |
| `service_role` (backend Flask) | acesso total, ignora RLS |

Isso garante o requisito: dados clínicos nunca ficam expostos publicamente.
