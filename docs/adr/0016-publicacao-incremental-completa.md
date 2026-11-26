# ADR-0016: Publicação somente após escopo incremental completo

**Status:** Proposed. **Data:** 2026-11-26.

O replace do ADR-0015 é atômico por arquivo, não por deploy. As specs
acumulativas podiam concluir com rejeições de chave antes do upsert. O CLI
aceitava alguns escopos parciais e o workflow publicava MVs e cache mesmo
depois de erro. Um retry com diff vazio não recria uma invalidação perdida.

## Decisão

Manter a atomicidade por arquivo e os hashes de negócio existentes. Falhar
antes do upsert se houver rejeições; a DLQ não compartilha o rollback.
Comitar dados, fase com identidade do CSV e pendência de invalidação na
mesma transação; incluir a marca no commit do último arquivo do bucket.
O runner para na primeira lacuna e o deploy não inicia a publicação de
um escopo incompleto. Isto substitui **somente** a decisão de refresh/warm
após erro do ADR-0015; suas guardas e backups continuam necessários.

## Consequências

A aplicação pode ficar desatualizada até que a lacuna seja reconciliada;
consultas diretas à base podem ver os commits anteriores. O artefato do
agendador não é publicado se o runner falhar. Conferir os arquivos confirmados,
marca, DLQ e `etl_cache_invalidation_queue` antes da retomada. A marca de
ingestão BF não é promovida pelo sucesso de um deploy de outra fonte. O
agendador consulta uma publicação BF bem-sucedida cujo escopo inclua a
competência informada; um artefato global legado não é prova desse escopo.
A fila não
reverte uma MV ou um cache já promovido. Falha de comunicação no COMMIT
exige inspeção da fase persistida, não presumir rollback.

Não reclassificar como dado válido uma linha antes rejeitada sem testar
o contrato de identidade correspondente, nem recalcular `_nk_md5` em massa.

Um 304 só dispensa a carga quando o token da aplicação corresponde à spec,
ao bucket e aos hashes dos objetos confirmados pela fonte. Token legado ou
ausente exige GET integral mesmo com CSV de nome idêntico em disco. O custo
desse primeiro ciclo e da comparação de payload em conflitos de chave
natural precisa ser medido em clone, com o mesmo volume da carga real.
