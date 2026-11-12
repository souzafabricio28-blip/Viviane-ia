from __future__ import annotations

import os
import subprocess
from datetime import datetime

from core.settings import settings
from core.voice import falar

_PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "imagens")
ESTILOS_DISPONIVEIS = [
    "Realista", "Cartoon", "Pintura a óleo", "Digital art", "Desenho animado",
    "Aquarela", "Fotografia", "Cinematográfico", "Cyberpunk", "Fantasia",
    "Steampunk", "Anime", "Mangá", "Pixel art", "3D render", "Esboço a lápis",
    "Carvão", "Arte vetorial", "Retro vintage", "Sci-fi", "Medieval", "Gótico",
    "Pop art", "Surrealista", "Minimalista", "Expressionista", "Impressionista",
    "Arte urbana (grafitti)", "Low poly", "Isométrico",
]

_PROMPTS_ESTILOS = {
    "Realista": "photorealistic, highly detailed, realistic lighting, 8K, sharp focus",
    "Cartoon": "cartoon style, cel shading, vibrant colors, comic style, bold outlines",
    "Pintura a óleo": "oil painting, textured brushstrokes, rich colors, canvas texture, classical painting",
    "Digital art": "digital artwork, crisp details, smooth rendering, concept art, trending on ArtStation",
    "Desenho animado": "animated cartoon, Disney style, colorful, whimsical, smooth lines",
    "Aquarela": "watercolor painting, soft washes, paper texture, flowing pigments, artistic",
    "Fotografia": "photograph, f/2.8, shallow depth of field, professional photo, natural lighting",
    "Cinematográfico": "cinematic, film still, dramatic lighting, movie scene, anamorphic lens, cinematic color grading",
    "Cyberpunk": "cyberpunk aesthetic, neon lights, rainy street, futuristic city, dark atmosphere, Blade Runner style",
    "Fantasia": "fantasy art, magical atmosphere, ethereal, mythical, epic fantasy illustration",
    "Steampunk": "steampunk, brass and copper, Victorian era, gears and cogs, retrofuturistic",
    "Anime": "anime style, Japanese animation, vibrant colors, large eyes, detailed background, Studio Ghibli inspired",
    "Mangá": "manga style, black and white line art, comic panel, screentone, Japanese comic",
    "Pixel art": "pixel art, 8-bit, retro game graphics, blocky pixels, chunky pixels, sprite style",
    "3D render": "3D render, octane render, realistic textures, global illumination, ray tracing, ultra detailed",
    "Esboço a lápis": "pencil sketch, graphite, rough lines, shading, hand-drawn, monochrome",
    "Carvão": "charcoal drawing, smudged, dark tones, textured paper, expressive strokes",
    "Arte vetorial": "vector art, flat design, clean lines, solid colors, scalable graphic, Adobe Illustrator",
    "Retro vintage": "retro style, vintage, 1950s aesthetic, faded colors, old photograph, nostalgic",
    "Sci-fi": "science fiction, futuristic, sleek design, advanced technology, spaceship, alien world",
    "Medieval": "medieval fantasy, castle, rustic, old world, renaissance fair, historical",
    "Gótico": "gothic style, dark, dramatic, Victorian gothic, moody, shadowy, cathedral",
    "Pop art": "pop art, Andy Warhol style, bold colors, comic book dots, screen print, iconic",
    "Surrealista": "surrealist, dreamlike, Salvador Dali style, impossible scenes, melting, bizarre",
    "Minimalista": "minimalist, simple, clean design, negative space, minimal, elegant, subtle",
    "Expressionista": "expressionist, bold brushstrokes, emotional, Edvard Munch style, intense colors",
    "Impressionista": "impressionist, Monet style, soft focus, light effects, plein air, pastel colors",
    "Arte urbana (grafitti)": "graffiti art, street art, spray paint, urban wall, stencil, Banksy style, vibrant splash",
    "Low poly": "low poly, geometric, faceted, polygon mesh, 3D low resolution, minimalist shapes",
    "Isométrico": "isometric view, 3D isometric, technical illustration, isometric perspective, clean geometry",
}

_NEGATIVO_PADRAO = "text, letters, watermark, signature, ugly, deformed, blurry, low quality, distorted"


def gerar_imagem(prompt: str, estilo: str | None = None) -> str:
    try:
        estilo_prompt = _PROMPTS_ESTILOS.get(estilo, "")
        prompt_final = f"{prompt}, {estilo_prompt}" if estilo_prompt else prompt
        caminho = _replicate(prompt_final)
        if caminho:
            os.startfile(caminho)
            falar("Imagem gerada com sucesso.")
            return f"Imagem salva em: {caminho}"
        falar("Não foi possível gerar a imagem.")
        return "Erro ao gerar imagem."
    except Exception as e:
        erro = f"Erro ao gerar imagem: {str(e)[:100]}"
        falar(erro)
        return erro


def _replicate(prompt: str) -> str | None:
    try:
        os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_key
        import replicate
        output = replicate.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": prompt,
                "negative_prompt": _NEGATIVO_PADRAO,
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "num_inference_steps": 25,
            },
        )
        url = output[0] if isinstance(output, list) else output
        return _baixar(url)
    except Exception as e:
        msg = str(e)
        if "402" in msg or "credit" in msg.lower():
            falar("Créditos do Replicate esgotados. Configure uma chave válida para gerar imagens.")
        else:
            falar(f"Falha ao gerar imagem: {msg[:60]}")
        return None


def _baixar(url: str) -> str | None:
    try:
        import requests
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        nome = f"viviane_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        caminho = os.path.join(_PASTA_IMAGENS, nome)
        with open(caminho, "wb") as f:
            f.write(resp.content)
        return caminho
    except Exception as e:
        print(f"  Erro ao baixar: {e}")
        return None
