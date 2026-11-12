from __future__ import annotations

import base64
import os
from datetime import datetime

from groq import Groq

from core.settings import settings
from core.voice import falar

_PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "imagens")


def analisar_ecra(pergunta: str) -> str:
    falar("A analisar o conteúdo do ecrã...")
    try:
        import pyautogui

        nome = f"print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        caminho = os.path.join(_PASTA_IMAGENS, nome)
        pyautogui.screenshot(caminho)
        with open(caminho, "rb") as f:
            imagem_b64 = base64.b64encode(f.read()).decode("utf-8")

        client = Groq(api_key=settings.groq_api_key)
        resposta = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": pergunta},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{imagem_b64}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.7,
            max_tokens=512,
        )
        texto = resposta.choices[0].message.content or "Não consegui analisar a imagem."
        falar(texto)
        return texto
    except Exception as e:
        erro = f"Erro ao analisar o ecrã: {str(e)[:100]}"
        falar(erro)
        return erro
    finally:
        try:
            os.remove(caminho)
        except Exception:
            pass
