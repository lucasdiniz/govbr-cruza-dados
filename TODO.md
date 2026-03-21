# TODO - govbr-cruza-dados

## Em andamento (processos rodando)
- [ ] Estabelecimentos 1-9 carregando (~30M restantes, rodando ha horas)
- [ ] PGFN recarga com datas corrigidas (40M registros)
- [ ] Viagens 2020-2022, 2025-2026 carregando

## Pendente (executar quando processos terminarem)
- [ ] Rodar `python -m etl.15_normalizar` (normalizar CPF/CNPJ para JOINs)
- [ ] Recriar views materializadas (`sql/12_views.sql`) apos normalizacao
- [ ] Validar contagens finais de todas as tabelas
- [ ] Rodar as 32 queries de fraude e verificar resultados

## Dados faltando (cobertura temporal 2020+)
- [x] CPGF 2020 (12 meses) — carregado
- [x] Viagens 2020-2022, 2025-2026 — carregando
- [x] SIAPE 202602 (mais recente) — carregado
- [ ] Verificar se Estabelecimentos0 do G:/ tem o mesmo conteudo que o do C:/

## Proxima iteracao: novas fontes de dados
- [ ] TSE Candidatos 2020-2024 (cadastro + patrimonio declarado + prestacao de contas)
  - URL: https://dadosabertos.tse.jus.br/dataset/candidatos-2024
  - Valor: cruzar patrimonio declarado com contratos de empresas do candidato
- [ ] Pessoas Expostas Politicamente (PEP)
  - URL: portaldatransparencia.gov.br/download-de-dados/pep (deu 403, tentar novamente)
  - Valor: PEP que e socio de fornecedora do governo
- [ ] Favorecidos PJ - Portal da Transparencia
  - Encontrado no dados.gov.br
  - Valor: todas as PJs que recebem pagamentos federais
- [ ] Notas Fiscais Eletronicas
  - URL: portaldatransparencia.gov.br/download-de-dados/notas-fiscais
  - Valor: superfaturamento, notas para empresas fantasma
- [ ] Bolsa Familia / Novo Bolsa Familia - Pagamentos
  - URL: portaldatransparencia.gov.br/download-de-dados
  - Valor: servidor ou socio de empresa recebendo BF indevidamente
- [ ] Explorar catalogo completo do dados.gov.br via API (chave: salva no .env)

## Melhorias tecnicas
- [ ] Otimizar _staging_copy do RFB (csv.reader Python e muito lento para 13GB)
  - Alternativa: usar COPY direto com QUOTE '"' e tratar erros por arquivo
- [ ] Adicionar script de validacao (compara wc -l dos CSVs com COUNT(*) das tabelas)
- [ ] Criar script para atualizar dados incrementalmente (nao recarregar tudo)
- [ ] Trocar senha do PostgreSQL (Gemini teve acesso via historico de conversa)
- [ ] Configurar max_wal_size no PostgreSQL (checkpoints muito frequentes nos logs)

## GitHub
- [ ] Resetar senha do GitHub e fazer push
  - Repo: github.com/lucasdiniz/govbr-cruza-dados
  - 7 commits prontos para push
- [ ] Adicionar .env ao .gitignore (ja esta, verificar)
- [ ] Remover chave API do dados.gov.br do historico de conversa (salvar em .env)

## Qualidade dos dados
- [ ] 101 registros de empresa com natureza_juridica corrompida (dados desalinhados por ; no CSV)
- [ ] CPGF: 25% das transacoes sem data (sigiloso) — normal, nao e bug
- [ ] Formato de CNPJ inconsistente entre fontes — resolvido com 15_normalizar
- [ ] Estabelecimentos: so Estab0 carregou do C:/, restante do G:/ quando .env mudou
