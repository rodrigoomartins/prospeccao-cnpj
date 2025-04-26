import os
import xmlrpc.client
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD')

# ATENÇÃO: Carregue também o dicionário de marcadores em algum momento
# mapa_marcadores = {"Nome do marcador": ID}  -> Te mostro já já abaixo

def conectar_odoo():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def enviar_para_odoo(empresa, vendedor_id=False, marcadores=[], mapa_marcadores=None):
    try:
        uid, models = conectar_odoo()

        # Preparação dos dados
        nome_fantasia = empresa.get('nome_fantasia') or ""
        razao_social = empresa.get('razao_social') or ""
        nome_exibicao = nome_fantasia.strip() or razao_social.strip() or "Empresa sem nome"

        cidade = empresa.get('Município') or ""
        estado = empresa.get('uf') or ""
        logradouro = empresa.get('logradouro') or ""
        numero = empresa.get('numero') or ""
        bairro = empresa.get('bairro') or ""
        cep = empresa.get('cep') or ""

        endereco = f"{logradouro}, {numero}, {bairro}, {cidade} - {estado}, CEP {cep}"

        ddd = str(empresa.get('ddd1', '')).strip()
        telefone = str(empresa.get('telefone1', '')).strip()

        if ddd and telefone:
            telefone_completo = f"({ddd}) {telefone}"
        elif telefone:
            telefone_completo = telefone
        else:
            telefone_completo = ""

        # Procurar parceiro existente
        parceiro_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'res.partner', 'search',
            [[['name', '=', nome_exibicao]]]
        )

        if parceiro_ids:
            parceiro_id = parceiro_ids[0]
        else:
            # Criar parceiro
            parceiro_id = models.execute_kw(
                ODOO_DB, uid, ODOO_PASSWORD,
                'res.partner', 'create',
                [{
                    'name': nome_exibicao,
                    'phone': telefone_completo,
                    'email': empresa.get('email', ''),
                    'city': cidade,
                    'street': endereco,
                    'zip': cep,
                }]
            )

        # Preparar criação da oportunidade
        lead_vals = {
            'name': nome_exibicao,
            'partner_id': parceiro_id,
            # 'company_name': nome_exibicao,  # IMPORTANTE para exibir Nome da Empresa no CRM
            'contact_name': nome_exibicao,
            'email_from': empresa.get('email', ''),
            'phone': telefone_completo,
            'street': endereco,
            'city': cidade,
            'zip': cep,
            'stage_id': 1,  # Qualificação de Oportunidades
            'type': 'opportunity',
            'description': f"Oportunidade gerada via ferramenta de prospecção Streamlit.",
            'user_id': vendedor_id if vendedor_id else False,
        }

        # Adicionar marcadores (tags) se selecionados
        if marcadores:
            # Converte nomes de marcadores para IDs
            tag_ids = [(6, 0, [mapa_marcadores[tag] for tag in marcadores])]
            lead_vals['tag_ids'] = tag_ids

        # Criar a oportunidade
        lead_id = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'crm.lead', 'create',
            [lead_vals]
        )

        return True

    except Exception as e:
        print(f"Erro ao criar oportunidade no Odoo: {e}")
        return False
