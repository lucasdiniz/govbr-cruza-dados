# Relatório de Auditoria: Contratos Assinados em Fins de Semana na Paraíba

**Data de Geração:** 28 de Março de 2026
**Base de Dados:** Query Q47 — contratos PNCP com dt_assinatura em sábado ou domingo
**Metodologia:** Identificação de contratos públicos cuja data de assinatura registrada no PNCP cai em sábado ou domingo.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração. A data de assinatura registrada no PNCP pode divergir da data efetiva (erro de digitação, registro retroativo, sistemas que registram a data de publicação e não de assinatura). A apuração compete aos órgãos de controle.

---

## 1. Resumo Executivo

Foram identificados **426 contratos** assinados em fins de semana na Paraíba desde 2022, totalizando **R$ 247,9 milhões** (R$165,8M aos sábados, R$82M aos domingos). Contratos assinados fora do horário de expediente levantam questões sobre a regularidade do processo administrativo, pois a administração pública opera em dias úteis.

---

## 2. Maiores Contratos em Fim de Semana

### 2.1. Fotovoltaico da Sec. da Fazenda de JP — R$ 96,8 milhões (Sábado, 19/10/2024)
- **Órgão:** Secretaria Municipal da Fazenda de João Pessoa
- **Fornecedor:** COESA — Corpo de Obras, Eletrificações e Soluções Ambientais Ltda
- **Objeto:** Sistema fotovoltaico para prédios públicos e iluminação pública
- **Valor:** R$ 96.828.965,69
- **Análise:** Maior contrato individual identificado. O valor expressivo e a assinatura em sábado justificam verificação da tramitação processual.

### 2.2. Equipamentos Educacionais — R$ 28,9 milhões (Domingo, 08/06/2025)
- **Órgão:** Secretaria de Estado da Educação e Ciência e Tecnologia
- **Fornecedor:** Sisttech Tecnologia Educacional S/A
- **Objeto:** Equipamentos para laboratórios de ensino
- **Valor:** R$ 28.939.648,00
- **Análise:** Contrato de quase R$29M assinado em domingo.

### 2.3. Material de Expediente CG — R$ 6,9 milhões (Sábado, 22/03/2025)
- **Órgão:** Município de Campina Grande
- **Fornecedor:** JR Comércio de Utilidades Ltda
- **Objeto:** Material de expediente
- **Valor:** R$ 6.984.499,51
- **Análise:** Valor elevado para material de expediente de um único município.

### 2.4. Obras de Drenagem JP — R$ 6,5 milhões (Sábado, 25/10/2025)
- **Órgão:** Secretaria Municipal da Fazenda de João Pessoa
- **Fornecedor:** Arko Construções Ltda
- **Objeto:** Drenagem e pavimentação em 16 ruas dos bairros Costa do Sol e Gramame

### 2.5. Reforma Escolar JP — R$ 5,7 milhões (Sábado, 07/02/2026)
- **Órgão:** Município de João Pessoa
- **Fornecedor:** Construtora Idenge Ltda
- **Objeto:** Ampliação e reforma da EMEF Dom Adauto

### 2.6. Evento Cultural — R$ 2 milhões (Domingo, 20/07/2025)
- **Órgão:** Secretaria de Estado da Cultura
- **Fornecedor:** Eleven Dragons Produções Ltda
- **Objeto:** Patrocínio do Imagineland On The Road 2025
- **Análise:** Contrato de evento cultural assinado em domingo.

---

## 3. Distribuição

| Dia | Contratos | Valor Total |
|-----|-----------|-------------|
| Sábado | 190 | R$ 165.843.063,93 |
| Domingo | 236 | R$ 82.056.662,38 |
| **Total** | **426** | **R$ 247.899.726,31** |

---

## 4. Possíveis Explicações

1. **Erro de registro:** O sistema PNCP pode registrar a data de publicação ou inclusão no sistema, não a data efetiva de assinatura
2. **Registro retroativo:** Contratos assinados em dia útil mas registrados no sistema durante o final de semana
3. **Contratos de emergência:** Situações excepcionais que demandam assinatura imediata
4. **Irregularidade processual:** Assinatura efetiva em dia não útil, sem expediente administrativo

---

## 5. Recomendações

1. **TCE-PB/CGE:** Verificar se os contratos de maior valor (> R$5M) foram efetivamente assinados nas datas registradas
2. **PNCP:** Avaliar se o campo `dt_assinatura` está sendo preenchido corretamente pelos órgãos paraibanos
3. **Órgãos contratantes:** Implementar validação no sistema que alerte quando data de assinatura cair em fim de semana

## Fontes
1. **PNCP:** Portal Nacional de Contratações Públicas, dados atualizados mar/2026
2. **Query Q47:** `queries/fraude_superfaturamento.sql`
