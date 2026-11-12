from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import Optional

import requests

from core.conversa import registrar
from core.settings import settings
from core.voice import falar

log = logging.getLogger("Viviane.Clima")

_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 600  # 10 min

# Códigos de condição do tempo (OpenWeatherMap)
CONDICOES_PT = {
    "clear sky": "céu limpo",
    "few clouds": "poucas nuvens",
    "scattered clouds": "nuvens dispersas",
    "broken clouds": "nuvens quebradas",
    "overcast clouds": "nublado",
    "light rain": "chuva leve",
    "moderate rain": "chuva moderada",
    "heavy intensity rain": "chuva forte",
    "very heavy rain": "chuva muito forte",
    "extreme rain": "chuva extrema",
    "freezing rain": "chuva congelante",
    "light intensity shower rain": "pancadas de chuva leve",
    "shower rain": "pancadas de chuva",
    "heavy intensity shower rain": "pancadas de chuva forte",
    "ragged shower rain": "chuva irregular",
    "light snow": "neve leve",
    "snow": "neve",
    "heavy snow": "neve forte",
    "sleet": "granizo",
    "mist": "névoa",
    "smoke": "fumaça",
    "haze": "neblina seca",
    "sand/dust whirls": "redemoinhos de poeira",
    "fog": "nevoeiro",
    "sand": "areia",
    "dust": "poeira",
    "volcanic ash": "cinzas vulcânicas",
    "squalls": "rajadas",
    "tornado": "tornado",
    "thunderstorm": "tempestade",
    "thunderstorm with light rain": "tempestade com chuva leve",
    "thunderstorm with rain": "tempestade com chuva",
    "thunderstorm with heavy rain": "tempestade com chuva forte",
    "light thunderstorm": "tempestade leve",
    "heavy thunderstorm": "tempestade forte",
}


def _traduzir_condicao(desc: str) -> str:
    return CONDICOES_PT.get(desc.lower(), desc)


# Códigos WMO usados pelo Open-Meteo (serviço gratuito, sem chave)
_WMO_PT = {
    0: "céu limpo", 1: "predomínio de sol", 2: "parcialmente nublado", 3: "nublado",
    45: "nevoeiro", 48: "nevoeiro com geada",
    51: "garoa leve", 53: "garoa", 55: "garoa forte",
    56: "garoa congelante", 57: "garoa congelante forte",
    61: "chuva leve", 63: "chuva moderada", 65: "chuva forte",
    66: "chuva congelante", 67: "chuva congelante forte",
    71: "neve leve", 73: "neve", 75: "neve forte", 77: "grãos de neve",
    80: "pancadas de chuva leves", 81: "pancadas de chuva", 82: "pancadas de chuva fortes",
    85: "pancadas de neve", 86: "pancadas de neve fortes",
    95: "tempestade", 96: "tempestade com granizo", 99: "tempestade com granizo forte",
}


def _limpar_cidade(cidade: str) -> str:
    """'Sao Paulo?' / 'são paulo, SP.' -> 'Sao Paulo' / 'são paulo' (só o nome da cidade)."""
    nome = (cidade or "").split(",")[0]
    nome = re.sub(r"[^\w\s'\-]", " ", nome, flags=re.UNICODE)
    nome = re.sub(r"^(?:em|na|no|de|do|da)\s+", "", nome.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", nome).strip() or "São Paulo"


def _open_meteo(sessao: requests.Session, cidade: str, dias: int = 1) -> tuple[str, str]:
    """Devolve (texto, erro). Sem chave de API: geocodifica e consulta o Open-Meteo."""
    nome = _limpar_cidade(cidade)
    geo = sessao.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": nome, "count": 5, "language": "pt", "format": "json"},
        timeout=8,
    ).json()
    locais = geo.get("results") or []
    if not locais:
        return "", f"Não encontrei a cidade {nome}. Tente outro nome."
    local = next((x for x in locais if x.get("country_code") == "BR"), locais[0])

    resp = sessao.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": local["latitude"], "longitude": local["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "weather_code,wind_speed_10m,pressure_msl",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                     "precipitation_probability_max,weather_code",
            "timezone": "auto", "wind_speed_unit": "ms", "forecast_days": max(1, dias),
        },
        timeout=8,
    )
    dados = resp.json()
    if resp.status_code != 200 or "current" not in dados:
        return "", "O serviço de clima não respondeu agora. Tente de novo em instantes."

    atual, diario = dados["current"], dados["daily"]
    lugar = local["name"] + (f", {local['admin1']}" if local.get("admin1") else "")
    if dias > 1:
        linhas = [f"Previsão para {lugar}:"]
        for i in range(min(dias, len(diario["time"]))):
            dia = datetime.strptime(diario["time"][i], "%Y-%m-%d").strftime("%d/%m")
            cond = _WMO_PT.get(diario["weather_code"][i], "tempo variável")
            chuva = diario["precipitation_probability_max"][i]
            extra = f", {chuva}% de chuva" if chuva else ""
            linhas.append(
                f"  {dia}: {diario['temperature_2m_min'][i]:.0f}°/{diario['temperature_2m_max'][i]:.0f}°C, {cond}{extra}"
            )
        return "\n".join(linhas), ""

    cond = _WMO_PT.get(atual["weather_code"], "tempo variável")
    chuva = diario["precipitation_probability_max"][0]
    texto = (
        f"Em {lugar}: {atual['temperature_2m']:.0f}°C (sensação {atual['apparent_temperature']:.0f}°C), "
        f"{cond}. Hoje entre {diario['temperature_2m_min'][0]:.0f}° e {diario['temperature_2m_max'][0]:.0f}°C"
        + (f", {chuva}% de chance de chuva" if chuva else "")
        + f". Umidade {atual['relative_humidity_2m']}%, vento {atual['wind_speed_10m']:.1f} m/s."
    )
    return texto, ""


class PrevisaoTempo:
    def __init__(self) -> None:
        self.api_key = settings.weather_api_key
        self._sessao = requests.Session()
        self._cidade_padrao = "São Paulo"

    def _falar_async(self, texto: str) -> None:
        """Fala sem bloquear (fire and forget)."""
        try:
            import threading
            threading.Thread(target=falar, args=(texto,), daemon=True).start()
        except Exception:
            pass

    def _previsao_gratis(self, cidade: str, dias: int, falar_resultado: bool) -> str:
        """Open-Meteo: funciona sem WEATHER_API_KEY."""
        chave = (_limpar_cidade(cidade).lower(), dias)
        em_cache = _CACHE.get(f"om:{chave}")
        if em_cache and time.time() - em_cache[1] < _CACHE_TTL:
            texto = em_cache[0]["texto"]
        else:
            try:
                texto, erro = _open_meteo(self._sessao, cidade, dias)
            except requests.ConnectionError:
                texto, erro = "", "Sem conexão com a internet para obter a previsão."
            except requests.Timeout:
                texto, erro = "", "O serviço do clima demorou muito para responder."
            except Exception as exc:
                log.warning("Open-Meteo falhou: %s", exc)
                texto, erro = "", "Não consegui obter a previsão agora."
            if erro:
                if falar_resultado:
                    self._falar_async(erro)
                return erro
            _CACHE[f"om:{chave}"] = ({"texto": texto}, time.time())

        registrar("assistente", f"[Clima] {texto}")
        if falar_resultado:
            self._falar_async(texto.split("\n")[0] if dias == 1 else f"Previsão dos próximos {dias} dias na tela.")
        return texto

    def obter_previsao(self, cidade: str = "", falar_resultado: bool = True) -> str:
        """Previsão atual."""
        if not cidade:
            cidade = self._cidade_padrao

        if not self.api_key:
            return self._previsao_gratis(cidade, 1, falar_resultado)

        cidade_norm = cidade.strip().title()
        agora = time.time()

        if cidade_norm in _CACHE:
            dados, timestamp = _CACHE[cidade_norm]
            if agora - timestamp < _CACHE_TTL:
                return self._formatar_atual(dados, cidade_norm, falar_resultado)

        try:
            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?q={quote(cidade_norm)}&appid={self.api_key}&lang=pt_br&units=metric"
            )
            resp = self._sessao.get(url, timeout=5)
            dados = resp.json()

            if resp.status_code == 404:
                msg = f"Não encontrei a cidade {cidade_norm}. Tente com estado: 'São Paulo, SP'"
                if falar_resultado:
                    self._falar_async(msg)
                return msg
            if resp.status_code == 401:
                return self._previsao_gratis(cidade_norm, 1, falar_resultado)
            if resp.status_code != 200:
                msg = f"Erro ao obter clima: {dados.get('message', 'erro desconhecido')}"
                if falar_resultado:
                    self._falar_async(msg)
                return msg

            _CACHE[cidade_norm] = (dados, time.time())
            return self._formatar_atual(dados, cidade_norm, falar_resultado)

        except requests.ConnectionError:
            msg = "Sem conexão com a internet para obter a previsão"
        except requests.Timeout:
            msg = "O serviço do clima demorou muito para responder"
        except Exception as exc:
            msg = f"Erro ao obter previsão: {exc}"
        if falar_resultado:
            self._falar_async(msg)
        return msg

    def _formatar_atual(self, dados: dict, cidade: str, falar_resultado: bool) -> str:
        temp = dados["main"]["temp"]
        sensacao = dados["main"]["feels_like"]
        desc = _traduzir_condicao(dados["weather"][0]["description"])
        umidade = dados["main"]["humidity"]
        vento = dados["wind"]["speed"]
        pressao = dados["main"]["pressure"]
        nascer = datetime.fromtimestamp(dados["sys"]["sunrise"]).strftime("%H:%M")
        por = datetime.fromtimestamp(dados["sys"]["sunset"]).strftime("%H:%M")

        texto = (
            f"Em {cidade}: {temp:.0f}°C (sensação {sensacao:.0f}°C). "
            f"{desc.capitalize()}. Umidade {umidade}%, vento {vento:.1f} m/s. "
            f"Pressão {pressao} hPa. Nascer {nascer}, pôr {por}."
        )
        registrar("assistente", f"[Clima] {texto}")
        if falar_resultado:
            self._falar_async(texto)
        return texto

    def obter_previsao_5dias(self, cidade: str = "", falar_resultado: bool = True) -> str:
        """Previsão 5 dias / 3 horas."""
        if not cidade:
            cidade = self._cidade_padrao

        if not self.api_key:
            return self._previsao_gratis(cidade, 5, falar_resultado)

        cidade_norm = cidade.strip().title()
        try:
            url = (
                "https://api.openweathermap.org/data/2.5/forecast"
                f"?q={quote(cidade_norm)}&appid={self.api_key}&lang=pt_br&units=metric"
            )
            resp = self._sessao.get(url, timeout=8)
            dados = resp.json()

            if resp.status_code != 200:
                msg = f"Erro: {dados.get('message', 'erro')}"
                if falar_resultado:
                    self._falar_async(msg)
                return msg

            # Agrupa por dia
            dias = {}
            for item in dados["list"]:
                dt = datetime.fromtimestamp(item["dt"])
                dia_key = dt.strftime("%d/%m")
                if dia_key not in dias:
                    dias[dia_key] = {"min": 99, "max": -99, "condicoes": [], "chuva": 0}
                dias[dia_key]["min"] = min(dias[dia_key]["min"], item["main"]["temp_min"])
                dias[dia_key]["max"] = max(dias[dia_key]["max"], item["main"]["temp_max"])
                dias[dia_key]["condicoes"].append(_traduzir_condicao(item["weather"][0]["description"]))
                dias[dia_key]["chuva"] += item.get("rain", {}).get("3h", 0)

            linhas = [f"Previsão 5 dias para {cidade_norm}:"]
            for i, (dia, info) in enumerate(list(dias.items())[:5]):
                cond = max(set(info["condicoes"]), key=info["condicoes"].count)
                chuva = f", chuva {info['chuva']:.1f}mm" if info["chuva"] > 0 else ""
                linhas.append(f"  {dia}: {info['min']:.0f}°/{info['max']:.0f}°C, {cond}{chuva}")

            texto = "\n".join(linhas)
            registrar("assistente", f"[Clima 5d] {texto}")
            if falar_resultado:
                # Fala resumo
                resumo = f"Próximos 5 dias em {cidade_norm}: " + ", ".join(
                    f"{d.split()[0]} {info['min']:.0f} a {info['max']:.0f} graus"
                    for d, info in list(dias.items())[:3]
                )
                self._falar_async(resumo)
            return texto

        except Exception as exc:
            msg = f"Erro na previsão 5 dias: {exc}"
            if falar_resultado:
                self._falar_async(msg)
            return msg

    def obter_alerta(self, cidade: str = "") -> Optional[str]:
        """Verifica alertas de tempo severo."""
        if not self.api_key:
            return None
        if not cidade:
            cidade = self._cidade_padrao
        try:
            # One Call API 3.0 precisa de lat/lon, usar geocoding primeiro
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={quote(cidade)}&limit=1&appid={self.api_key}"
            geo_resp = self._sessao.get(geo_url, timeout=3)
            if geo_resp.status_code != 200 or not geo_resp.json():
                return None
            loc = geo_resp.json()[0]
            lat, lon = loc["lat"], loc["lon"]

            onecall_url = (
                f"https://api.openweathermap.org/data/3.0/onecall"
                f"?lat={lat}&lon={lon}&appid={self.api_key}&lang=pt_br"
            )
            oc_resp = self._sessao.get(onecall_url, timeout=5)
            if oc_resp.status_code != 200:
                return None
            data = oc_resp.json()
            alerts = data.get("alerts", [])
            if alerts:
                return f"⚠️ Alerta: {alerts[0]['event']} - {alerts[0]['description'][:200]}"
        except Exception:
            pass
        return None


class ClimaManager:
    """Gerencia múltiplas cidades favoritas e alertas automáticos."""

    def __init__(self, previsao: PrevisaoTempo):
        self.previsao = previsao
        self.cidades_favoritas: list[str] = []
        self._carregar_favoritas()
        self._alertas_ativos: set[str] = set()

    def _carregar_favoritas(self):
        try:
            import json
            from core.settings import settings
            f = settings.data_dir / "cidades_favoritas.json"
            if f.exists():
                self.cidades_favoritas = json.loads(f.read_text())
        except Exception:
            pass

    def _salvar_favoritas(self):
        try:
            import json
            from core.settings import settings
            f = settings.data_dir / "cidades_favoritas.json"
            f.write_text(json.dumps(self.cidades_favoritas, ensure_ascii=False))
        except Exception:
            pass

    def adicionar_favorita(self, cidade: str) -> str:
        cidade_norm = cidade.strip().title()
        if cidade_norm not in self.cidades_favoritas:
            self.cidades_favoritas.append(cidade_norm)
            self._salvar_favoritas()
            return f"{cidade_norm} adicionada aos favoritos"
        return f"{cidade_norm} já está nos favoritos"

    def remover_favorita(self, cidade: str) -> str:
        cidade_norm = cidade.strip().title()
        if cidade_norm in self.cidades_favoritas:
            self.cidades_favoritas.remove(cidade_norm)
            self._salvar_favoritas()
            return f"{cidade_norm} removida dos favoritos"
        return f"{cidade_norm} não está nos favoritos"

    def listar_favoritas(self) -> str:
        if not self.cidades_favoritas:
            return "Nenhuma cidade favorita. Use 'adicionar cidade X aos favoritos'"
        return "Cidades favoritas: " + ", ".join(self.cidades_favoritas)

    def resumo_manha(self) -> str:
        """Resumo matinal para todas as cidades favoritas."""
        if not self.cidades_favoritas:
            return ""
        partes = []
        for cidade in self.cidades_favoritas[:3]:
            try:
                texto = self.previsao.obter_previsao(cidade, falar_resultado=False)
                partes.append(texto)
            except Exception:
                pass
        if partes:
            return "Bom dia! Resumo do tempo:\n" + "\n".join(partes)
        return ""

    def verificar_alertas(self) -> list[str]:
        alertas = []
        for cidade in self.cidades_favoritas:
            alerta = self.previsao.obter_alerta(cidade)
            if alerta and alerta not in self._alertas_ativos:
                self._alertas_ativos.add(alerta)
                alertas.append(alerta)
        return alertas