# Briefing Diário — Área administrativa independente

Aplicação Next.js pronta para ser colocada na pasta `admin/` do mesmo repositório do Briefing Diário e publicada como projeto separado no Vercel.

## O que já está incluído

- Login real com Supabase Auth, reservado a `geral.amsol@gmail.com`.
- Gestão de contactos interessados no produto.
- Teste gratuito único de 48 horas.
- Registo e confirmação manual de pagamentos.
- Ativação automática da subscrição depois da confirmação.
- Datas de término calculadas por plano: semanal, mensal, trimestral, semestral e anual.
- Histórico das ações da força de trabalho agêntica.
- Base preparada para ligar Pay IZI/e-Mola quando os dados do comerciante forem recebidos.

## 1. Adicionar ao GitHub

Copie esta pasta completa, com o nome `admin`, para a raiz do repositório existente:

```text
Briefing_Di-rio-/
├── admin/              ← esta aplicação
├── index.html          ← site atual (exemplo)
└── ...
```

Depois faça commit e push normalmente.

## 2. Preparar o Supabase

1. Crie um projeto em [supabase.com](https://supabase.com).
2. Abra **SQL Editor**, cole todo o conteúdo de `supabase/schema.sql` e execute.
3. Abra **Authentication → Users → Add user**.
4. Crie o utilizador `geral.amsol@gmail.com`, escolha uma palavra-passe forte e marque o email como confirmado.
5. Em **Project Settings → API**, copie:
   - Project URL
   - Publishable key
   - Service role key

Nunca exponha nem publique a service role key.

## 3. Publicar no Vercel

1. No Vercel, escolha **Add New → Project**.
2. Importe o mesmo repositório GitHub do Briefing Diário.
3. Em **Root Directory**, selecione `admin`.
4. Adicione estas variáveis em **Settings → Environment Variables**:

| Variável | Valor |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL do Supabase |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Publishable key do Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key do Supabase |
| `ADMIN_EMAIL` | `geral.amsol@gmail.com` |

5. Clique em **Deploy**.

O Vercel tratará esta pasta como um projeto separado, sem alterar o site público atual. Cada novo `git push` voltará a publicar automaticamente.

## 4. Testar localmente (opcional)

Requer Node.js 22 ou mais recente.

```bash
cp .env.example .env.local
npm install
npm run dev
```

Abra `http://localhost:3000` e entre com o utilizador criado no Supabase.

## Fluxo de acesso

1. Registar o contacto.
2. Ativar o teste gratuito de 48 horas, se aplicável.
3. Quando houver pagamento, registar o plano, a referência e o telefone pagador.
4. Confirmar a transação no Pay IZI/e-Mola.
5. Clicar em **Confirmar** no painel.
6. A subscrição é criada ou prolongada e termina automaticamente na data calculada.

## Planos configurados

| Plano | Preço |
|---|---:|
| Semanal | 92 MT |
| Mensal | 250 MT |
| Trimestral | 700 MT |
| Semestral | 1.250 MT |
| Anual | 2.500 MT |

## Segurança

- As rotas administrativas confirmam a sessão e o email autorizado no servidor.
- A service role key existe apenas nas variáveis secretas do Vercel.
- Row Level Security está ativa nas quatro tabelas.
- Não coloque `.env.local` no GitHub.

## Próxima integração

Quando chegarem os dados definitivos do comerciante Pay IZI, será possível substituir a confirmação manual por validação automática sem mudar a estrutura principal do painel.
