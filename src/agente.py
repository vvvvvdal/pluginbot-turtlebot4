import ollama

MODELO = "llama3.2:1b"
PROMPT = (
    """
    You are a robot inspection system.
    Analyze the following text from a QR code.
    If the text indicates a success, normal status, or no errors (e.g., contains 'sucess', 'success', 'clear', 'completed'), return EXACTLY this JSON: {"action": "continue"}
    If the text indicates a failure, structural error, or requires attention (e.g., contains 'error', 'fail', 'critical', 'alert'), return EXACTLY this JSON: {"action": "fix"}
    Do not output any other text, only the JSON.
    """
)

class Agente:
    def __init__(self):
        self.modelo = MODELO
        self.prompt = PROMPT

    def interpretar_ordem(self, texto):
        mensagens = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": texto}
        ]

        resposta = ollama.chat(model=self.modelo, messages=mensagens)
        conteudo = resposta.message.content.lower()

        if 'continue' in conteudo:
            return {'action': 'continue'}
        elif 'fix' in conteudo:
            return {'action': 'fix'}
        else:
            print(f"[AGENTE] Resposta confusa do agente de IA: {conteudo}")
            return {'action': 'fix'} # fix por segurança

