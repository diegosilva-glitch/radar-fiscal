#!/usr/bin/env python3
"""
Radar Fiscal — script de atualização automática.

O que este script faz:
  1. Lê site/data.json (estado atual do painel).
  2. Chama a API da Anthropic (modelo Claude) com a ferramenta de busca na
     web habilitada, pedindo para verificar os portais oficiais listados
     abaixo e trazer só atualizações REAIS, com fonte e data.
  3. Valida o formato da resposta. Se vier fora do formato esperado, o
     script ABORTA sem sobrescrever nada (fail-safe: prefere não atualizar
     a colocar lixo/alucinação no ar).
  4. Recalcula o Boletim do Dia a partir dos itens mais recentes.
  5. Grava site/data.json de volta.

O que este script NÃO faz (por limitação técnica e/ou de segurança):
  - Não varre o LinkedIn (colegasHoje / meusPostsLinkedIn continuam como
    estavam). Automatizar login/scraping do LinkedIn violaria os Termos de
    Uso da plataforma e arrisca a conta do usuário — por isso isso
    continua sendo feito manualmente, sob pedido, dentro da conversa com o
    Claude.
  - Não decide sozinho mudanças de estrutura do site (novas abas, etc.) —
    só atualiza o conteúdo dos itens já mapeados.
"""

import json
import os
import sys
from datetime import datetime, timezone

import anthropic

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "site", "data.json")

FONTES_OFICIAIS = """
- Receita Federal: https://www.gov.br/receitafederal/pt-br
- Diário Oficial da União / Imprensa Nacional: https://www.gov.br/imprensanacional/pt-br
- CONFAZ: https://www.confaz.fazenda.gov.br/
- STF: https://portal.stf.jus.br
- STJ: https://www.stj.jus.br
- SEFAZ-SP (legislação): https://legislacao.fazenda.sp.gov.br
- SEFAZ-MT: https://www5.sefaz.mt.gov.br
- SEFA-PA: https://www.sefa.pa.gov.br
- SEFAZ-TO: https://www.to.gov.br/sefaz/
- SEFAZ-MS: https://www.sefaz.ms.gov.br
- Secretaria da Economia-GO: https://goias.gov.br/economia/
- Secretaria Municipal da Fazenda de São Paulo: https://prefeitura.sp.gov.br/web/fazenda
- Secretaria de Finanças de Barueri: https://portal.barueri.sp.gov.br
- Portal do Simples Nacional (RFB): https://www8.receita.fazenda.gov.br/SimplesNacional/
- Comitê Gestor do IBS: https://www.cgibs.gov.br
"""

SYSTEM_PROMPT = f"""Você é o motor de atualização do painel "Radar Fiscal".
Sua única tarefa é verificar, usando a ferramenta de busca na web, se as
fontes oficiais abaixo têm novidades tributárias desde a última varredura,
e devolver ISSO em JSON estrito, sem nenhum texto fora do JSON.

Fontes oficiais a verificar:
{FONTES_OFICIAIS}

Regras inegociáveis:
1. NUNCA invente uma norma, portaria, decreto, data ou número. Se não
   encontrar nada novo e verificável para uma fonte, simplesmente não
   inclua um item novo para ela — não é obrigatório ter novidade toda vez.
2. Todo item novo precisa ter uma URL real de onde a informação foi
   confirmada (campo "url"), e "real" deve ser sempre true.
3. Não repita itens que já existem no array atual (comparar por título/
   conteúdo) — só adicione o que for genuinamente novo desde a data mais
   recente já presente.
4. Responda APENAS com um objeto JSON válido no formato:
{{
  "novos_itens": [
    {{
      "id": <inteiro, maior que o maior id já existente>,
      "esfera": "federal" | "estadual" | "municipal",
      "estado": "MT" | "PA" | "TO" | "MS" | "GO" | "SP" (só se esfera=estadual),
      "municipio": "SP" | "Barueri" (só se esfera=municipal),
      "fonte": "<nome do órgão>",
      "url": "<url real>",
      "real": true,
      "titulo": "<título curto e direto>",
      "resumo": "<2-3 frases explicando o impacto prático>",
      "tags": ["..."],
      "data": "YYYY-MM-DD",
      "tipo": "<tipo do ato: Portaria, Decreto, Ato COTEPE, etc>"
    }}
  ],
  "estadosInfo_atualizacoes": {{ "MT": "<nova ultimaReal ou omitir se sem novidade>", ... }},
  "municipiosInfo_atualizacoes": {{ "SP": "<...>", "Barueri": "<...>" }}
}}
Se não houver nada novo em lugar nenhum, responda com:
{{"novos_itens": [], "estadosInfo_atualizacoes": {{}}, "municipiosInfo_atualizacoes": {{}}}}
"""


def carregar_dados():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_dados(dados):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def montar_prompt_usuario(dados):
    itens_atuais = dados.get("itens", [])
    maior_id = max((i.get("id", 0) for i in itens_atuais), default=0)
    resumo_itens = "\n".join(
        f"- [{i.get('data')}] {i.get('titulo')}" for i in itens_atuais
    )
    return f"""Maior id já usado no array de itens: {maior_id} (novos itens devem ter id > {maior_id}).

Itens já existentes no radar (não repita estes; só adicione o que for
genuinamente novo e mais recente que eles):
{resumo_itens}

Verifique agora as fontes oficiais e devolva o JSON conforme instruído."""


def validar_resposta(obj):
    if not isinstance(obj, dict):
        return False
    if "novos_itens" not in obj or not isinstance(obj["novos_itens"], list):
        return False
    for item in obj["novos_itens"]:
        campos_obrigatorios = ["id", "esfera", "fonte", "url", "real", "titulo", "resumo", "tags", "data", "tipo"]
        if not all(c in item for c in campos_obrigatorios):
            return False
        if item.get("real") is not True:
            return False
        if not item.get("url", "").startswith("http"):
            return False
    return True


def recalcular_boletim(itens):
    reais = [i for i in itens if i.get("real")]
    reais_ordenados = sorted(reais, key=lambda i: i.get("data", ""), reverse=True)[:6]
    def rotulo(i):
        if i["esfera"] == "federal":
            return "Federal"
        if i["esfera"] == "estadual":
            return f"Estadual/{i.get('estado','?')}"
        return f"Municipal/{i.get('municipio','?')}"
    return {
        "data": datetime.now().strftime("%d de %B de %Y"),
        "itens": [
            {"titulo": f"[{rotulo(i)}] {i['titulo']}", "desc": i["resumo"]}
            for i in reais_ordenados
        ],
    }


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERRO: variável de ambiente ANTHROPIC_API_KEY não definida.", file=sys.stderr)
        sys.exit(1)

    dados = carregar_dados()
    client = anthropic.Anthropic(api_key=api_key)

    prompt_usuario = montar_prompt_usuario(dados)

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt_usuario}],
    )

    # Junta todos os blocos de texto da resposta final (pode ter buscas no meio)
    texto_final = "".join(
        bloco.text for bloco in resp.content if getattr(bloco, "type", None) == "text"
    )

    texto_limpo = texto_final.strip()
    if texto_limpo.startswith("```"):
        texto_limpo = texto_limpo.strip("`")
        if texto_limpo.startswith("json"):
            texto_limpo = texto_limpo[4:]

    try:
        resultado = json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        print(f"ERRO: resposta do modelo não é JSON válido, abortando sem alterar nada. Detalhe: {e}", file=sys.stderr)
        print("Resposta recebida:", texto_final[:2000], file=sys.stderr)
        sys.exit(1)

    if not validar_resposta(resultado):
        print("ERRO: JSON não passou na validação de esquema, abortando sem alterar nada.", file=sys.stderr)
        print(json.dumps(resultado, ensure_ascii=False, indent=2)[:2000], file=sys.stderr)
        sys.exit(1)

    novos = resultado["novos_itens"]
    if novos:
        dados["itens"].extend(novos)
        print(f"{len(novos)} item(ns) novo(s) adicionado(s).")
    else:
        print("Nenhuma novidade real encontrada nesta varredura.")

    for estado, texto in resultado.get("estadosInfo_atualizacoes", {}).items():
        if estado in dados.get("estadosInfo", {}):
            dados["estadosInfo"][estado]["ultimaReal"] = texto

    for municipio, texto in resultado.get("municipiosInfo_atualizacoes", {}).items():
        if municipio in dados.get("municipiosInfo", {}):
            dados["municipiosInfo"][municipio]["ultimaReal"] = texto

    dados["boletimHoje"] = recalcular_boletim(dados["itens"])
    dados["ultimaAtualizacao"] = datetime.now(timezone.utc).astimezone().strftime("%d/%m %H:%M")

    salvar_dados(dados)
    print("data.json atualizado com sucesso.")


if __name__ == "__main__":
    main()
