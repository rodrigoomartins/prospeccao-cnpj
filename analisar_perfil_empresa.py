import re
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.chrome.service import Service as ChromeService
import numpy as np

ARQUIVO_ANALISE = "analises_empresas.csv"

def iniciar_navegador():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# def carregar_html(url):
#     driver = iniciar_navegador()
#     driver.get(url)
#     time.sleep(3)
#     html = driver.page_source
#     driver.quit()
#     return html

def carregar_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text

def analisar_perfil_empresa(url):
    try:
        html = carregar_html(url)
        soup = BeautifulSoup(html, "html.parser")

        termos = []
        termos_busca = ["atacado", "varejo", "revenda", "distribuidor", "lojista", "representante", "comprar", "venda"]
        texto_site = soup.get_text(separator=" ").lower()

        for termo in termos_busca:
            if termo in texto_site:
                termos.append(termo)

        if "atacado" in termos or "distribuidor" in termos or "revenda" in termos:
            perfil = "Atacado"
        elif "varejo" in termos or "comprar" in termos:
            perfil = "Varejo"
        else:
            perfil = "Indefinido"

        return {"perfil": perfil, "termos_detectados": termos}

    except Exception as e:
        print(f"Erro ao analisar perfil: {e}")
        return {"perfil": "Indefinido", "termos_detectados": []}

def analisar_precos(url):
    try:
        html = carregar_html(url)
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"Erro ao carregar a página: {e}")
        return {
            "quantidade_precos": 0,
            "preco_minimo": 0,
            "preco_maximo": 0,
            "preco_medio": 0,
            "precos": []
        }

    precos = []

    # Padrões regex
    padrao_preco_real = re.compile(r"R\$[\s]*([\d\.]+,[\d]{2})")
    padrao_preco_simples = re.compile(r"([\d\.]+,[\d]{2})")

    textos = soup.find_all(text=True)

    palavras_proibidas = ["x", "parcelas", "sem juros", "parcela", "vezes"]

    def texto_possui_parcelamento(texto):
        texto = texto.lower()
        return any(palavra in texto for palavra in palavras_proibidas)

    # 1 - Preços "R$ 99,90" (normal)
    for texto in textos:
        if texto_possui_parcelamento(texto):
            continue  # Ignora textos de parcelamento
        
        matches = padrao_preco_real.findall(texto)
        for match in matches:
            valor = match.replace(".", "").replace(",", ".")
            try:
                precos.append(float(valor))
            except:
                continue

    # 2 - Preços tipo "99,90" sem "R$"
    for texto in textos:
        if texto_possui_parcelamento(texto):
            continue
        
        matches = padrao_preco_simples.findall(texto)
        for match in matches:
            valor = match.replace(".", "").replace(",", ".")
            try:
                preco = float(valor)
                if 5 < preco < 50000:
                    precos.append(preco)
            except:
                continue

    # 3 - Busca em classes/ids típicos
    seletor_precos = soup.select('[class*="price"], [class*="valor"], [id*="price"], [id*="valor"]')
    for tag in seletor_precos:
        texto = tag.get_text(strip=True)
        if texto_possui_parcelamento(texto):
            continue
        
        matches = padrao_preco_simples.findall(texto)
        for match in matches:
            valor = match.replace(".", "").replace(",", ".")
            try:
                preco = float(valor)
                if 5 < preco < 50000:
                    precos.append(preco)
            except:
                continue

    # 4 - Busca em meta tags tipo product:price
    metas = soup.find_all("meta", attrs={"property": "product:price:amount"})
    for meta in metas:
        try:
            valor = float(meta["content"])
            precos.append(valor)
        except:
            continue

    # 5 - Busca em JSON embutido
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                offers = data.get("offers")
                if isinstance(offers, dict) and "price" in offers:
                    valor = float(offers["price"])
                    precos.append(valor)
                elif isinstance(offers, list):
                    for offer in offers:
                        if "price" in offer:
                            valor = float(offer["price"])
                            precos.append(valor)
        except Exception:
            continue

    precos = list(set([p for p in precos if p > 5]))

    if not precos:
        return {
            "quantidade_precos": 0,
            "preco_minimo": 0,
            "preco_maximo": 0,
            "preco_medio": 0,
            "precos": []
        }

    preco_min = min(precos)
    preco_max = max(precos)
    preco_medio = sum(precos) / len(precos)

    return {
        "quantidade_precos": len(precos),
        "preco_minimo": round(preco_min, 2),
        "preco_maximo": round(preco_max, 2),
        "preco_medio": round(preco_medio, 2),
        "precos": precos
    }

def carregar_analises():
    """
    Carrega o arquivo de análises comerciais, se existir. Caso contrário, cria um DataFrame vazio com as colunas corretas.
    """
    arquivo = "analises_empresas.csv"
    colunas = [
        "cnpj", "razao_social", "data_analise", "url_site",
        "perfil", "termos_detectados", "quantidade_precos",
        "preco_minimo", "preco_maximo", "preco_medio", "precos"
    ]

    if os.path.exists(arquivo):
        df = pd.read_csv(arquivo, sep=";", dtype=str)

        # Se as colunas obrigatórias não existirem (arquivo corrompido ou vazio)
        if "cnpj" not in df.columns:
            df = pd.DataFrame(columns=colunas)
    else:
        df = pd.DataFrame(columns=colunas)

    return df

def salvar_analise_comercial(cnpj, razao_social, url_site, perfil, termos_detectados, resultado_precos):
    """
    Salva ou atualiza a análise comercial da empresa no CSV analises_empresas.csv
    """
    arquivo_analises = "analises_empresas.csv"

    # Garante que temos os dados em strings corretas
    termos_detectados_str = json.dumps(termos_detectados, ensure_ascii=False)
    precos_str = json.dumps(resultado_precos.get("precos", []), ensure_ascii=False)

    registro = {
        "cnpj": cnpj,
        "razao_social": razao_social,
        "data_analise": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "url_site": url_site,
        "perfil": perfil,
        "termos_detectados": termos_detectados_str,
        "quantidade_precos": resultado_precos.get("quantidade_precos", 0),
        "preco_minimo": resultado_precos.get("preco_minimo", 0),
        "preco_maximo": resultado_precos.get("preco_maximo", 0),
        "preco_medio": resultado_precos.get("preco_medio", 0),
        "precos": precos_str
    }

    if os.path.exists(arquivo_analises):
        df = pd.read_csv(arquivo_analises, sep=";", dtype=str)

        # Garante que existe a coluna cnpj
        if "cnpj" not in df.columns:
            df = pd.DataFrame(columns=registro.keys())

        # Atualiza se já existir o cnpj
        if cnpj in df["cnpj"].values:
            df.loc[df["cnpj"] == cnpj, list(registro.keys())] = list(registro.values())
        else:
            novo_registro = pd.DataFrame([registro])
            df = pd.concat([df, novo_registro], ignore_index=True)
    else:
        df = pd.DataFrame([registro])

    df.to_csv(arquivo_analises, sep=";", index=False, encoding="utf-8-sig")