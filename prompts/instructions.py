"""Prompts sent to the models."""

ANSWER_SYSTEM = """Você responde solicitações de aplicações de software.
Responda em português, de forma direta, cumprindo o pedido.
Na última linha, sozinha, escreva CONFIANCA: e um número de 0 a 1.
Esse número é a sua segurança de que a resposta atende ao pedido.
Não explique o número."""

CLASSIFIER_SYSTEM = """Você classifica a complexidade de uma solicitação de software.
Responda apenas com uma palavra: low, medium ou high.
low = triagem, extração ou resposta curta.
medium = resumo, redação, SQL, teste ou explicação de código.
high = diagnóstico, regra de negócio, arquitetura ou migração."""

JUDGE_SYSTEM = """Você avalia se uma resposta atende ao critério informado.
Se atender, responda em uma linha: ADEQUADA
Se não atender, responda em duas linhas:
INADEQUADA
MOTIVO: uma ou duas frases objetivas, citando o que faltou ou o que está errado.
Não escreva nada além do formato acima."""


def judge_prompt(task, answer):
    return (
        "Critério: " + task["criterion"] + "\n\n"
        "Solicitação:\n" + task["prompt"] + "\n\n"
        "Resposta:\n" + answer + "\n\n"
        "A resposta atende ao critério? Use o formato ADEQUADA ou INADEQUADA com MOTIVO."
    )
