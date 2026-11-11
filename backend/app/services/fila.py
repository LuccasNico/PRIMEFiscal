"""Fila de processamento das notas.

O banco é a própria fila: toda nota com status "pendente" está aguardando. Uma única thread
retira a mais antiga, processa e grava o resultado. Processar uma nota por vez é proposital:
um modelo local não aguenta requisições em paralelo, e na API paga isso limita o gasto.

Como os PDFs ficam guardados em disco, a fila sobrevive a um reinício do servidor.
"""

import logging
import threading

from sqlalchemy import select, update

from app import armazenamento
from app.db import NotaFiscalRegistro, SessaoLocal, agora
from app.schemas.nota_fiscal import Metadados, NotaFiscalExtraida, ResultadoValidacao, StatusNota
from app.services.ia import ErroExtracao
from app.services.processamento import Abordagem, processar_pdf

log = logging.getLogger(__name__)

# A thread é acordada a cada envio; este intervalo é só uma garantia caso um aviso se perca
INTERVALO_DE_VERIFICACAO_SEGUNDOS = 5

Resultado = tuple[NotaFiscalExtraida, ResultadoValidacao, Metadados]


class FilaDeProcessamento:
    def __init__(self) -> None:
        self._ha_trabalho = threading.Event()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    def iniciar(self) -> None:
        self._retomar_interrompidas()
        self._parar.clear()
        self._thread = threading.Thread(target=self._executar, name="fila-de-notas", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self._ha_trabalho.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def avisar(self) -> None:
        """Acorda a thread: há nota nova na fila."""
        self._ha_trabalho.set()

    def _retomar_interrompidas(self) -> None:
        """Notas que estavam em processamento quando o servidor parou voltam para a fila."""
        with SessaoLocal() as sessao:
            sessao.execute(
                update(NotaFiscalRegistro)
                .where(NotaFiscalRegistro.status == StatusNota.PROCESSANDO.value)
                .values(status=StatusNota.PENDENTE.value, iniciado_em=None)
            )
            sessao.commit()

    def _executar(self) -> None:
        while not self._parar.is_set():
            try:
                processou = self.processar_proxima()
            except Exception:
                # Uma falha aqui (ex.: banco indisponível) não pode derrubar a fila inteira
                log.exception("Falha inesperada na fila de processamento")
                processou = False
            if not processou:
                self._ha_trabalho.wait(timeout=INTERVALO_DE_VERIFICACAO_SEGUNDOS)
                self._ha_trabalho.clear()

    def processar_proxima(self) -> bool:
        """Processa a nota pendente mais antiga. Retorna False se a fila está vazia."""
        with SessaoLocal() as sessao:
            registro = sessao.scalars(
                select(NotaFiscalRegistro)
                .where(NotaFiscalRegistro.status == StatusNota.PENDENTE.value)
                .order_by(NotaFiscalRegistro.enfileirado_em, NotaFiscalRegistro.id)
                .limit(1)
            ).first()
            if registro is None:
                return False
            registro.status = StatusNota.PROCESSANDO.value
            registro.iniciado_em = agora()
            sessao.commit()
            nota_id = registro.id
            abordagem = Abordagem(registro.abordagem or Abordagem.PDF.value)

        # A chamada à IA pode levar minutos: nenhuma sessão do banco fica aberta enquanto isso
        resultado, erro = self._extrair(nota_id, abordagem)

        with SessaoLocal() as sessao:
            registro = sessao.get(NotaFiscalRegistro, nota_id)
            if registro is None:  # removida durante o processamento
                return True
            if resultado is None:
                registro.status, registro.erro = StatusNota.ERRO.value, erro
            else:
                dados, validacao, metadados = resultado
                registro.tipo_documento = dados.tipo_documento.value
                registro.dados = dados.model_dump(mode="json")
                registro.validacao = validacao.model_dump(mode="json")
                registro.metadados = metadados.model_dump(mode="json")
                registro.status = (StatusNota.PROCESSADA if validacao.valido else StatusNota.REVISAR).value
                registro.erro = None
            sessao.commit()
        return True

    def _extrair(self, nota_id: int, abordagem: Abordagem) -> tuple[Resultado | None, str | None]:
        try:
            pdf_bytes = armazenamento.ler_pdf(nota_id)
        except FileNotFoundError:
            return None, "O PDF original não está mais disponível no servidor. Envie o arquivo novamente."
        try:
            return processar_pdf(pdf_bytes, abordagem), None
        except ErroExtracao as e:
            return None, str(e)
        except Exception:
            # Qualquer outro erro fica restrito a esta nota; as próximas da fila seguem normalmente
            log.exception("Erro inesperado ao processar a nota %s", nota_id)
            return None, "Erro inesperado ao processar o documento. Veja os detalhes no log do servidor."


fila = FilaDeProcessamento()
