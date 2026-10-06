from unittest.mock import Mock

import pytest


# Classe simuladora do Módulo de Prontuário Eletrônico (PEP) que envia dados
class ProntuarioService:
    def __init__(self, gateway_faturamento_client):
        self.gateway = gateway_faturamento_client

    def finalizar_atendimento(self, id_atendimento, valor_float, token_seguro):
        # Conversão de formato de dados para evitar o Bug do Ponto Decimal:
        # R$ 150.00 deve virar 15000 centavos (inteiro).
        # round() evita erros de ponto flutuante (ex.: 19.99 * 100 = 1998.999...)
        valor_centavos = int(round(valor_float * 100))

        payload = {
            "id_atendimento": id_atendimento,
            "valor_consulta": valor_centavos,
        }

        headers = {"Authorization": f"Bearer {token_seguro}"}

        # Faz a chamada de integração para a API do faturamento
        return self.gateway.post("/guias", json=payload, headers=headers)


# --- SUÍTE DE TESTES DE INTEGRAÇÃO ---

def test_integracao_sucesso_formato_dados():
    # 1. Mock do cliente HTTP do Faturamento
    mock_client = Mock()
    # Atenção: o atributo correto é return_value (o original tinha "return_return_value",
    # que não configura nada e faria o post() devolver outro Mock).
    mock_client.post.return_value = {"status_code": 201, "id_guia": "GUI-9988"}

    servico_pep = ProntuarioService(mock_client)

    # 2. Chamada de integração
    resposta = servico_pep.finalizar_atendimento("ATT-123", 150.00, "TOKEN_VALIDO")

    # 3. Asserts
    # a) O método post foi chamado pelo prontuário
    assert mock_client.post.called
    mock_client.post.assert_called_once()

    # b) O status_code retornado foi o esperado (201)
    assert resposta["status_code"] == 201
    assert resposta["id_guia"] == "GUI-9988"

    # c) Mitigação do Bug do Ponto Decimal: o payload enviado tem inteiro em centavos
    _, kwargs = mock_client.post.call_args
    assert kwargs["json"]["valor_consulta"] == 15000
    assert isinstance(kwargs["json"]["valor_consulta"], int)

    # d) Cabeçalho de autorização no formato exigido
    assert kwargs["headers"]["Authorization"] == "Bearer TOKEN_VALIDO"


def test_integracao_falha_autenticacao():
    mock_client = Mock()
    # Simula erro de autenticação (token inválido/expirado) com HTTP 401
    mock_client.post.return_value = {"status_code": 401, "error": "Unauthorized"}

    servico_pep = ProntuarioService(mock_client)

    resposta = servico_pep.finalizar_atendimento("ATT-123", 150.00, "TOKEN_EXPIRADO")

    # 4. O status code retornado da chamada simulada deve ser 401
    assert resposta["status_code"] == 401
    assert resposta["error"] == "Unauthorized"
    # O token expirado realmente foi enviado ao faturamento
    _, kwargs = mock_client.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer TOKEN_EXPIRADO"


# --- EXTRA (Questão 3): simulação de timeout ---

def test_integracao_timeout_faturamento():
    mock_client = Mock()
    # side_effect com exceção simula a API fora do ar / rede oscilando
    mock_client.post.side_effect = TimeoutError("Timeout de conexão")

    servico_pep = ProntuarioService(mock_client)

    with pytest.raises(TimeoutError):
        servico_pep.finalizar_atendimento("ATT-123", 150.00, "TOKEN_VALIDO")

    # A chamada foi tentada; o sistema real deve capturar essa exceção,
    # salvar o prontuário localmente e enfileirar a guia (ver Q3 no relatório).
    mock_client.post.assert_called_once()
