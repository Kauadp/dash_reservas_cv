import pandas as pd
import requests

def converte_float(val):
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0

def fetch_reservas_cvcrm(url_base: str, headers: dict) -> pd.DataFrame:
    """
    Função para buscar reservas no CV CRM e retornar um DataFrame limpo.
    """
    params = {
        "faturar": "false",
        "condicao_completa": "true",
        "campos_adicionais_reserva_contrato": "true",
        "pagina": 1,
        "registros_por_pagina": 500,
    }
    response = requests.get(url_base, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"Erro ao buscar dados: {response.status_code} - {response.text}")

    if response.status_code == 200:
        dados_brutos = response.json()

    reservas_limpas = []

    # Garante que iteramos corretamente sobre os itens do dicionário
    lista_itens = (
        dados_brutos.values() if isinstance(dados_brutos, dict) else dados_brutos
    )

    for key, item in (
        dados_brutos.items() if isinstance(dados_brutos, dict) else enumerate(lista_itens)
    ):
        if not isinstance(item, dict):
            continue

        # --- Extração dos Sub-objetos Seguros ---
        situacao_info = item.get("situacao") or {}
        unidade_info = item.get("unidade") or {}
        titular_info = item.get("titular") or {}
        imobiliaria_info = item.get("imobiliaria") or {}
        corretor_info = item.get("corretor") or {}
        condicoes_info = item.get("condicoes") or {}
        comissoes_info = item.get("comissoes") or {}

        reservas_limpas = []

        if isinstance(dados_brutos, dict):
            iterator = dados_brutos.items()
        elif isinstance(dados_brutos, list):
            iterator = [(item.get("idproposta_cv", i), item) for i, item in enumerate(dados_brutos)]
        else:
            iterator = []

        for key, item in iterator:
            if not isinstance(item, dict):
                continue

            situacao_info = item.get("situacao") or {}
            unidade_info = item.get("unidade") or {}
            titular_info = item.get("titular") or {}
            imobiliaria_info = item.get("imobiliaria") or {}
            corretor_info = item.get("corretor") or {}
            condicoes_info = item.get("condicoes") or {}

            area_m2 = converte_float(unidade_info.get("area_privativa"))
            valor_contrato = converte_float(
                condicoes_info.get("valor_contrato")
                or condicoes_info.get("total_proposta")
            )
            valor_por_m2 = round(valor_contrato / area_m2, 2) if area_m2 > 0 else 0.0

            reserva_dict = {
                "id_reserva": str(key),
                "id_proposta_cv": item.get("idproposta_cv"),
                "id_proposta_int": item.get("idproposta_int"),
                "data_cadastro": item.get("data"),
                "data_venda": item.get("data_venda"),
                "data_contrato": item.get("data_contrato"),
                "data_cancelamento": item.get("data_cancelamento"),
                "vendida_flag": item.get("vendida", "N"),
                "id_situacao": situacao_info.get("idsituacao"),
                "situacao": situacao_info.get("situacao"),
                "grupo_situacao": situacao_info.get("grupo"),
                "tipo_venda": item.get("tipovenda"),
                "tipo_reserva": item.get("tiporeserva"),
                "empreendimento": unidade_info.get("empreendimento"),
                "id_empreendimento_cv": unidade_info.get("idempreendimento_cv"),
                "etapa": unidade_info.get("etapa"),
                "bloco_pavilhao": unidade_info.get("bloco"),
                "estande_unidade": unidade_info.get("unidade"),
                "id_unidade_cv": unidade_info.get("idunidade_cv"),
                "tipologia": unidade_info.get("tipologia"),
                "posicao": unidade_info.get("posicao"),
                "area_m2": area_m2,
                "valor_contrato": valor_contrato,
                "valor_por_m2": valor_por_m2,
                "vpl_reserva": converte_float(condicoes_info.get("vpl_reserva")),
                "vgv_tabela": converte_float(condicoes_info.get("vgv_tabela")),
                "total_proposta": converte_float(condicoes_info.get("total_proposta")),
                "valor_comissao": converte_float(item.get("valor_comissao")),
                "titular_nome": titular_info.get("nome"),
                "id_pessoa_cv": titular_info.get("idpessoa_cv"),
                "titular_doc_tipo": titular_info.get("documento_tipo"),
                "titular_documento": titular_info.get("documento"),
                "titular_cidade": titular_info.get("cidade"),
                "titular_estado": titular_info.get("estado"),
                "titular_email": titular_info.get("email"),
                "titular_telefone": titular_info.get("telefone")
                or titular_info.get("celular"),
                "como_ficou_sabendo": titular_info.get("como_ficou_sabendo"),
                "imobiliaria_nome": imobiliaria_info.get("nome"),
                "corretor_nome": corretor_info.get("corretor"),
                "corretor_email": corretor_info.get("email"),
                "observacoes": item.get("observacoes"),
                "aprovada_financeiramente": item.get("aprovada_financeiramente"),
                "solicitacao_distrato": item.get("solicitacao_distrato"),
            }

            campos_add = item.get("campos_adicionais") or []
            if isinstance(campos_add, list):
                for campo in campos_add:
                    if isinstance(campo, dict) and campo.get("nome"):
                        col_name = f"custom_{campo.get('nome').lower().replace(' ', '_')}"
                        reserva_dict[col_name] = campo.get("valor")

            reservas_limpas.append(reserva_dict)

        return pd.DataFrame(reservas_limpas)
