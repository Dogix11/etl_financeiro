
  
# Fluxo de Caixa Automatizado - ETL Financeiro com LLM

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?logo=googlegemini&logoColor=white)


## O Projeto
Uma arquitetura de dados *end-to-end* desenvolvida em Python e conteinerizada via Docker, projetada para automatizar a ingestão e estruturação de gastos pessoais, além de manter uma divisão igualitária das contas conjuntas. 

O sistema utiliza um Bot do Telegram como interface de entrada, processa os dados com a Vertex AI (Gemini 2.5 Pro) através de *prompts* dinâmicos e alimenta um Data Warehouse local em PostgreSQL, garantindo resiliência e consistência de dados em todas as etapas.

---

## Arquitetura do Pipeline

A arquitetura segue o padrão *Medallion* (Bronze, Silver, Gold), com um forte foco em resiliência transacional através do padrão Outbox, garantindo que nenhuma transação seja perdida em caso de falhas de rede ou indisponibilidade de APIs.

```mermaid
flowchart TD
    subgraph Ingestao [Telegram Bot]
        A1[Fatura <br> PDF]
        A2[Nota <br> Imagem +/- Texto]
        A3[Gasto <br> Texto]
    end

    subgraph Camada_Bronze [Raw & State Management]
        B[(Datalake / Volumes <br> JSON & Mídias)]
        Outbox[[Tabela Outbox <br> Controle de Estado, Logs e Retries]]
    end

    A1 -->|Payload Bruto| B
    A2 -->|Payload Bruto| B
    A3 -->|Payload Bruto| B
    
    A1 -->|Registra Evento pendente| Outbox
    A2 -->|Registra Evento pendente| Outbox
    A3 -->|Registra Evento pendente| Outbox

    subgraph Processamento_Assincrono [Processamento Assíncrono]
        W[Worker <br> Lê Outbox]
        LLM{Vertex AI <br> Prompts Dinâmicos}
    end

    Outbox -->|Consome Fila| W
    W <-->|OCR, Parse & Enriquecimento| LLM
    W -->|Atualiza Status: Sucesso ou Falha| Outbox

    subgraph Camada_Silver [Cleansed, Parsed & Enriched]
        S1[(faturas)]
        S2[(notas_fiscais)]
        S3[(itens_nota_fiscal)]
        S4[(transacoes_financeiras)]
        S5[(movimentacoes_financeiras <br> Livro Razão)]
    end

    W -->|Estruturação relacional| S1
    W -->|Estruturação relacional| S2
    W -->|Estruturação relacional| S4
    W -->|Enriquecimento de filhos| S3
    W -->|Geração de registro contábil| S5

    subgraph Integracoes_Externas [Integrações Externas]
        GS[(Google Sheets <br> Planilha de Rateio)]
    end

    S5 -.->|Sincroniza divisão de custos conjuntas| GS
    
    Ouro[(Camada Gold)]
    S5 -.->|Futuro: dbt| Ouro
```

### Camada Bronze (Raw) & Resiliência
*   **Ingestão Multifonte:** O bot possui funções distintas que aceitam formatos variados, o que determina o roteamento e os *prompts* dinâmicos subsequentes:
    1.  **Fatura:** Ingestão de documentos PDF.
    2.  **Nota:** Ingestão de imagens (fotos de cupons fiscais) acompanhadas ou não de texto de apoio.
    3.  **Gasto:** Descrição textual direta de uma movimentação.
*   **Armazenamento e Outbox:** O *payload* bruto é salvo no datalake (volumes Docker), enquanto um registro é criado na tabela **Outbox**. Essa tabela atua como a espinha dorsal de resiliência da aplicação: gerencia o estado de cada processamento, armazena logs detalhados e garante que, em caso de erro (ex: *timeout* da LLM), o evento fique pendente para *retry*, impedindo perda de dados (problema clássico no mundo real).

### Camada Silver (Cleansed/Parsed/Enriched)
*   **Processamento & Prompts Dinâmicos:** O *Worker* consome os eventos do Outbox e envia para a Vertex AI utilizando um *prompt* específico para cada tipo de entrada (Fatura, Nota ou Gasto).
*   **Modelagem Relacional (5 Tabelas):** Os dados não-estruturados são divididos, enriquecidos e tipados em cinco entidades principais:
    1.  `silver.faturas`
    2.  `silver.notas_fiscais`
    3.  `silver.itens_nota_fiscal` (Enriquecimento em nível de item, permitindo o acompanhamento de inflação pessoal e viabilizando futuros algoritmos de *Machine Learning* para otimização de compras).
    4.  `silver.transacoes_financeiras` (Compras individuais no cartão).
    5.  `silver.movimentacoes_financeiras` (O Livro Razão universal, que unifica PIX, despesas sem nota e os rateios).
*   **Sincronização com Google Sheets:** Quando o processamento identifica um gasto conjunto (regra de rateio entre Diogo e Flora), além de alimentar o Livro Razão, o sistema realiza uma integração secundária para registrar e atualizar os valores em uma planilha compartilhada no Google Sheets, mantendo a transparência em tempo real.

### Camada Gold (Analytics) *Em breve*
*   Modelagem dimensional via **dbt** voltada para BI e criação de visões analíticas agregadas.

---

## Destaques de Engenharia

*   **Tolerância a Falhas (Real-World Resilience):** Uso profundo do *Outbox Pattern*. Falhas de rede, indisponibilidade da Vertex AI ou instabilidades no Telegram não geram perda de informações. Tudo é enfileirado, logado e passível de reprocessamento autônomo.
*   **FinOps & Observabilidade:** Rastreamento ponta a ponta do consumo da LLM (latência, `prompt_tokens`, `output_tokens`, `total_tokens` e `thoughts_tokens`) atrelado a cada requisição na base de dados, permitindo a extração do custo unitário por processamento.
*   **Clean Architecture:** Separação estrita de responsabilidades (`delivery`, `usecases`, `services`, `infrastructure`), garantindo baixo acoplamento e facilitando a manutenção e a criação de testes.
*   **Idempotência e Segurança:** Tratamento robusto para evitar duplicações (*constraints* lógicas e físicas no BD), exclusão lógica (*soft delete*), e controle de acesso baseado no ID do Telegram (RBAC), protegendo a aplicação contra interações não autorizadas.

---

## Stack Tecnológico

<div align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Vertex_AI_(Gemini)-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white" alt="Ubuntu Server" />
  <img src="https://img.shields.io/badge/Telegram_API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram API" />
  <img src="https://img.shields.io/badge/Google_Sheets-34A853?style=for-the-badge&logo=googlesheets&logoColor=white" alt="Google Sheets API" />
</div>

<br>

*   **Bibliotecas Principais:** `python-telegram-bot`, `google-genai`, `pypdf`, `psycopg2`

---

## Estrutura do Repositório

```text
├── app/
│   ├── delivery/        # Interfaces externas (Telegram Handlers)
│   ├── usecases/        # Regras de negócio (ex: cálculos de rateio, roteamento de prompts)
│   ├── services/        # Integração com APIs externas (Vertex AI, Google Sheets)
│   ├── infrastructure/  # Repositórios, acesso ao Postgres, Gerenciamento do Outbox
│   └── main.py          # Entrypoint e injeção de dependências
├── volumes/             # Datalake (Camada Bronze Mídias) e persistência do Postgres
├── docker-compose.yml   # Declaração dos containers
├── requirements.txt     # Dependências Python
└── README.md
```

---

## Roadmap & Próximos Passos (A Evolução para MDS)

- [ ] **Orquestração com Apache Airflow:** Transição do loop assíncrono do *worker* para DAGs gerenciadas e agendadas, centralizando a observabilidade.
- [ ] **Transformação com dbt:** Adoção do *Data Build Tool* para materialização de regras de negócio complexas, reconciliação de datas e testes de qualidade de dados (Data Contracts) na camada Gold.
- [ ] **Data Visualization:** *Deploy* do Metabase para a criação de *dashboards* interativos de acompanhamento financeiro conjunto.