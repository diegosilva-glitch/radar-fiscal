# Radar Fiscal | Diego Santos — Automação

Este pacote faz o Radar Fiscal se atualizar sozinho 4x por dia (06:00, 12:00,
18:00 e 00:00, horário de Brasília), usando GitHub Actions + a API da
Anthropic com busca na web.

## O que tem aqui
- `site/` — o painel (index.html, data.json, manifest, ícones, service worker)
- - `scripts/update_radar.py` — o script que faz a varredura e atualiza `site/data.json`
  - - `.github/workflows/atualizar-radar.yml` — o agendador (roda o script nos 4 horários)
   
    - ## Passo a passo para colocar no ar (uma vez só)
   
    - ### 1. Repositório GitHub
    - Já criado: diegosilva-glitch/radar-fiscal
   
    - ### 2. Gerar a chave da Anthropic
    - 1. Vá em console.anthropic.com, crie conta e cadastre um método de pagamento.
      2. 2. Em "API Keys", crie uma nova chave (nome sugerido: radar-fiscal).
         3. 3. Copie o valor (começa com sk-ant-...) — cole só no passo 3, nunca em outro lugar (nem aqui no chat).
           
            4. ### 3. Guardar a chave como "Secret" no GitHub (nunca no código)
            5. 1. No repositório, vá em Settings -> Secrets and variables -> Actions.
               2. 2. Clique em New repository secret.
                  3. 3. Nome: ANTHROPIC_API_KEY. Valor: cole a chave copiada no passo 2.
                     4. 4. Salve.
                       
                        5. ### 4. Conectar o repositório ao Netlify
                        6. 1. No app.netlify.com, clique em Add new site -> Import an existing project.
                           2. 2. Escolha GitHub, autorize o acesso, selecione o repositório radar-fiscal.
                              3. 3. Em "Base directory"/"Publish directory", aponte para a pasta site.
                                 4. 4. Deploy. A partir de agora, todo push no repositório republica o site sozinho.
                                    5. 5. Clique em "Make public" nesse novo site também.
                                      
                                       6. ### 5. Testar manualmente
                                       7. 1. No GitHub, aba Actions do repositório.
                                          2. 2. Clique no workflow "Atualizar Radar Fiscal".
                                             3. 3. Clique em Run workflow pra rodar na hora, sem esperar o horário agendado.
                                                4. 4. Acompanhe o log — se der erro de validação, o script aborta sem publicar dado errado.
                                                  
                                                   5. ## Limitações
                                                   6. - A aba "Redes Sociais" (posts de colegas do LinkedIn) não é atualizada por este robô — automatizar login/scraping do LinkedIn violaria os Termos de Uso da plataforma. Isso continua manual, sob pedido, na conversa com o Claude.
                                                      - - O script só adiciona itens confirmados por busca na web, com URL real. Sem novidade real, o painel não ganha item novo naquele ciclo — isso é esperado.
                                                        - - Custo: cada execução chama a API da Anthropic. Rodando 4x/dia, tende a ficar baixo, mas acompanhe o faturamento em console.anthropic.com.
                                                          - 
