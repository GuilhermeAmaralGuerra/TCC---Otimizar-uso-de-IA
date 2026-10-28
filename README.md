# Otimização do Uso de Inteligência Artificial em Aplicações de Software

### Custos, Seleção de Modelos e Desempenho

Projeto experimental desenvolvido como parte do Trabalho de Conclusão de Curso (TCC) do **Centro Universitário Una**, em 2026.

## 1. Sobre o projeto

A integração de modelos de linguagem (LLMs) em aplicações de software permite automatizar tarefas, processar informações e apoiar a tomada de decisões. Entretanto, a utilização desses modelos por meio de APIs introduz desafios relacionados ao custo de inferência, ao tempo de resposta e à qualidade das respostas geradas.

Este projeto investiga estratégias para otimizar a utilização de modelos de Inteligência Artificial, avaliando se modelos menores e de menor custo conseguem atender satisfatoriamente a tarefas de diferentes níveis de complexidade.

O estudo também analisa mecanismos de roteamento, cascatas de modelos e compressão textual simplificada.

## 2. Objetivo

Comparar diferentes estratégias de seleção e utilização de modelos de linguagem, considerando:

- Custo estimado de inferência por requisição;
- Consumo de tokens de entrada e saída;
- Latência das respostas;
- Adequação das respostas às tarefas solicitadas;
- Comportamento de modelos de diferentes capacidades;
- Efeito do roteamento e do escalonamento entre modelos.

A hipótese investigada é que modelos de menor custo podem apresentar desempenho satisfatório em determinadas tarefas, tornando desnecessária a utilização de modelos maiores em todas as solicitações.

## 3. Tecnologias utilizadas

- **Python:** implementação do experimento e das estratégias.
- **OpenAI API:** acesso aos modelos de linguagem.
- **CSV:** armazenamento dos resultados experimentais.
- **Bibliotecas Python:** dependências especificadas em `requirements.txt`.
- **Git e GitHub:** versionamento e disponibilização do código-fonte.

## 4. Metodologia experimental

O experimento foi estruturado como uma pesquisa quantitativa e experimental.

Foram selecionadas **30 tarefas**, distribuídas igualmente entre três níveis de complexidade:

| Complexidade | Quantidade |
|---|---:|
| Baixa | 10 |
| Média | 10 |
| Alta | 10 |
| **Total** | **30** |

As tarefas envolveram classificação, extração de informações, geração de consultas SQL, elaboração de testes, interpretação de problemas e atividades de maior complexidade.

Cada tarefa foi submetida a oito estratégias, totalizando **240 execuções experimentais**, com uma execução por combinação de tarefa e estratégia.

### 4.1. Modelos avaliados

Foram utilizados três perfis de capacidade:

| Perfil | Modelo |
|---|---|
| Pequeno | `gpt-5.4-nano` |
| Médio | `gpt-5.4-mini` |
| Grande | `gpt-5.4` |

### 4.2. Estratégias avaliadas

**1. Modelo pequeno fixo**

Todas as solicitações são processadas pelo modelo pequeno.

**2. Modelo médio fixo**

Todas as solicitações são processadas pelo modelo médio.

**3. Modelo grande fixo**

Todas as solicitações são processadas pelo modelo grande.

**4. Roteamento por complexidade**

Um classificador analisa a solicitação e direciona a tarefa ao perfil considerado mais adequado.

**5. Cascata com limiar 0,70**

A execução começa no modelo pequeno. O escalonamento é realizado quando a confiança autodeclarada fica abaixo de 0,70.

**6. Cascata com limiar 0,80**

Utiliza o mesmo mecanismo, com limiar de confiança de 0,80.

**7. Cascata com limiar 0,90**

Aplica um critério mais restritivo para a manutenção da resposta no modelo atual.

**8. Compressão textual simplificada com roteamento**

Remove palavras frequentes (*stopwords*) do texto de entrada antes do roteamento, investigando os efeitos dessa redução sobre o custo e a qualidade das respostas.

Essa estratégia representa uma implementação simplificada de compressão textual, não uma implementação do algoritmo LLMLingua.

## 5. Métricas coletadas

Para cada execução, o software registra informações sobre:

- Identificação da tarefa e estratégia utilizada;
- Modelos acionados e perfil final;
- Quantidade de chamadas realizadas;
- Tokens de entrada e saída;
- Custo estimado em dólares;
- Latência da execução;
- Resposta gerada;
- Classificação de adequação;
- Justificativa do avaliador automático.

O custo de inferência é estimado com base no consumo de tokens informado pela API e nos preços configurados no experimento.

Custos associados à avaliação automática e outras despesas não são necessariamente incluídos no custo médio de inferência apresentado nas comparações.

Para a análise da latência, foi utilizado o método do intervalo interquartil (IQR) para identificar valores discrepantes.

## 6. Avaliação das respostas

A avaliação inicial foi realizada automaticamente por um modelo de linguagem, considerando critérios definidos para cada tarefa.

As respostas foram classificadas inicialmente em duas categorias:

- Adequada;
- Inadequada.

Posteriormente, os 15 registros classificados como inadequados foram submetidos a uma segunda avaliação assistida por IA, com conferência humana prevista no processo de revisão.

Na análise complementar, foram utilizadas três categorias:

- Adequada;
- Adequada com ressalvas;
- Inadequada.

As classificações originais foram preservadas para permitir a comparação dos julgamentos.

## 7. Resultados experimentais

A tabela apresenta os resultados obtidos na execução experimental.

| Estratégia | Adequação | Custo médio (US$) | Latência média (ms) |
|---|---:|---:|---:|
| Pequeno | 90,0% | 0,000631 | 3554 |
| Médio | 93,3% | 0,001466 | 2575 |
| Grande | 93,3% | 0,006982 | 5975 |
| Roteamento | 93,3% | 0,005579 | 5773 |
| Cascata 0,70 | 96,7% | 0,000615 | 3832 |
| Cascata 0,80 | 96,7% | 0,000976 | 4673 |
| Cascata 0,90 | 90,0% | 0,002262 | 4785 |
| Compressão + roteamento | 96,7% | 0,006411 | 6389 |

Os percentuais de adequação correspondem à avaliação automática original. A latência apresentada considera o tratamento dos valores discrepantes.

### 7.1. Comparação entre modelos fixos

O modelo pequeno alcançou 90,0% de adequação, enquanto o modelo grande atingiu 93,3%.

Apesar da pequena diferença de adequação observada, o custo médio do modelo grande foi aproximadamente onze vezes superior ao custo do modelo pequeno.

### 7.2. Comportamento das cascatas

A distribuição dos perfis finais foi:

| Estratégia | Pequeno | Médio | Grande |
|---|---:|---:|---:|
| Cascata 0,70 | 30 | 0 | 0 |
| Cascata 0,80 | 26 | 4 | 0 |
| Cascata 0,90 | 14 | 15 | 1 |

A cascata 0,70 manteve todas as solicitações no modelo pequeno durante a execução observada.

Com limiares mais restritivos, houve aumento no escalonamento para modelos de maior capacidade.

### 7.3. Revisão das classificações inadequadas

A segunda avaliação das 15 respostas inicialmente reprovadas apresentou:

| Classificação | Quantidade | Percentual |
|---|---:|---:|
| Adequada | 5 | 33,3% |
| Adequada com ressalvas | 8 | 53,3% |
| Inadequada | 2 | 13,3% |
| **Total** | **15** | **100,0%** |

Esses resultados indicam possíveis inconsistências na avaliação automática inicial, especialmente em tarefas que apresentavam ambiguidades ou exigências de formatação.

As classificações complementares não foram utilizadas para substituir os percentuais originais da comparação entre estratégias.

## 8. Estrutura do projeto

O repositório está organizado em módulos que separam a execução do experimento, os serviços, as configurações e os resultados.

```text
projeto_TCC/
├── controller/
├── prompts/
├── resultados_usados_tcc/
├── service/
├── utils/
├── main.py
├── requirements.txt
├── .env.template
├── .gitignore
└── README.md
```

A pasta `resultados_usados_tcc/` contém os arquivos disponibilizados para análise e documentação dos experimentos.

## 9. Instalação

### 9.1. Clonar o repositório

```bash
git clone https://github.com/GuilhermeAmaralGuerra/TCC---Otimizar-uso-de-IA.git
cd TCC---Otimizar-uso-de-IA
```

### 9.2. Criar um ambiente virtual

```bash
python -m venv venv
```

No Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source venv/bin/activate
```

### 9.3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 9.4. Configurar as credenciais

Utilize o arquivo `.env.template` como referência para criar um arquivo `.env` local.

Preencha as variáveis necessárias, incluindo a chave de acesso à API.

**Nunca publique sua chave de API no repositório.**

### 9.5. Executar o projeto

O projeto possui o arquivo `main.py` como ponto de entrada:

```bash
python main.py
```

A execução das estratégias depende das configurações e credenciais de API e pode gerar custos financeiros.

## 10. Limitações

Os resultados devem ser interpretados considerando as seguintes limitações:

- Uma execução por combinação de tarefa e estratégia;
- Conjunto experimental de 30 tarefas;
- Possíveis variações nas respostas dos modelos;
- Confiança autodeclarada e não calibrada nas cascatas;
- Possíveis inconsistências do avaliador automático;
- Oscilações de latência e infraestrutura;
- Custos calculados segundo os preços configurados;
- Ausência de demonstração de generalização estatística para outros conjuntos de tarefas.

## 11. Considerações finais

Os resultados experimentais sugerem que modelos de menor custo podem atender satisfatoriamente a diferentes solicitações e que a utilização indiscriminada de modelos mais avançados nem sempre representa a alternativa economicamente mais eficiente.

As estratégias de roteamento e cascata demonstraram comportamentos distintos conforme os critérios utilizados, enquanto a compressão simplificada não assegurou redução do custo total no conjunto avaliado.

O estudo também evidencia a necessidade de avaliar a confiabilidade das métricas de qualidade utilizadas na comparação entre modelos.

## 12. Referências principais

- CHEN, L.; ZAHARIA, M.; ZOU, J. *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance*. 2023.
- DING, B. et al. *Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing*. ICLR, 2024.
- STRIPELIS, D. et al. *TensorOpera Router: A Multi-Model Router for Efficient LLM Inference*. EMNLP Industry Track, 2024.
- DEKONINCK, J.; BAADER, M.; VECHEV, M. *A Unified Approach to Routing and Cascading for LLMs*. 2024.

As referências bibliográficas completas estão disponíveis no artigo acadêmico correspondente.

## 13. Autoria e finalidade

Projeto desenvolvido para fins acadêmicos no Centro Universitário Una, em 2026.

Este repositório disponibiliza uma implementação experimental e dados de avaliação de estratégias de utilização de modelos de linguagem.

A execução do projeto pode consumir créditos de serviços externos de IA.