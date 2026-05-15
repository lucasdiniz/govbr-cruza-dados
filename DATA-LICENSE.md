# Nota sobre licenciamento de dados

A licença [MIT](LICENSE) deste repositório cobre **apenas o código-fonte**.

## Dados públicos

Os datasets que o ETL baixa e cruza vêm de múltiplas fontes públicas
brasileiras (Receita Federal, PNCP, TCE-PB, dados.pb.gov.br, TSE, PGFN, SIAPE,
Bolsa Família, CPGF, BNDES, ComprasNet, emendas parlamentares, sanções,
renúncias fiscais, viagens a serviço, acordos de leniência etc.). Cada fonte é
regida por seus próprios termos — tipicamente:

- [Lei de Acesso à Informação (Lei 12.527/2011)](http://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm)
- [Lei Geral de Proteção de Dados (Lei 13.709/2018)](http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- Termos de uso específicos divulgados no portal de cada órgão

Consulte o portal oficial da fonte antes de redistribuir os dados ou
construir produtos derivados.

## Dados pessoais (LGPD)

O projeto trata dados pessoais (CPFs parciais, vínculos servidor × empresa,
benefícios sociais etc.) na fronteira do que a LGPD define como interesse
público em transparência. As bases legais típicas para esse tipo de
tratamento são, no entendimento do mantenedor:

- **Art. 7º III** — *"administração pública, para o tratamento e uso
  compartilhado de dados necessários à execução de políticas públicas"*
- **Art. 7º IV** — *"realização de estudos por órgão de pesquisa, garantida,
  sempre que possível, a anonimização"*
- **Art. 26** — regime de uso compartilhado de dados pelo Poder Público
  (regime sob o qual a fonte original divulga os dados)

**Esta nota não é parecer jurídico.** O mantenedor é pessoa física e não
substitui consulta a advogado. Se você for reusar este projeto (especialmente
para fins comerciais ou para tratar volumes maiores que os já publicados),
consulte um especialista LGPD.

## Convenções de mascaramento

Quando o projeto exibe CPF em UI pública ou em relatórios versionados, usa
o padrão canônico `***.NNN.NNN-**` (mantém só os 6 dígitos centrais — bate
com a coluna `cpf_digitos_6` das materialized views).

`scripts/audit_report_identifiers.py --strict` valida que nenhum CPF
formatado completo (`NNN.NNN.NNN-NN`) tenha vazado para os relatórios
markdown versionados.

## Reportar exposição de dados pessoais

- [GitHub Security Advisory](https://github.com/lucasdiniz/govbr-cruza-dados/security/advisories) (canal privado)
- [contato@transparenciapb.org](mailto:contato@transparenciapb.org)
- Política completa de privacidade em desenvolvimento (será `docs/privacidade.md`)
