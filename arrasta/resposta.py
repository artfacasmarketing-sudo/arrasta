"""Tira o JSON de dentro da resposta colada da IA (com ou sem ```json, com ou sem texto em volta)."""
import json


class RespostaInvalida(Exception):
    pass


def extrair(texto):
    texto = texto.strip().lstrip("﻿")
    if not texto:
        raise RespostaInvalida("a resposta está vazia")
    dec = json.JSONDecoder()
    achados = []
    i = texto.find("{")
    while i != -1:
        try:
            obj, fim = dec.raw_decode(texto, i)
            if isinstance(obj, dict):
                achados.append(obj)
            i = texto.find("{", fim)
        except json.JSONDecodeError:
            i = texto.find("{", i + 1)
    com_slides = [o for o in achados if "slides" in o]
    if len(com_slides) == 1:
        return com_slides[0]
    if len(com_slides) > 1:
        raise RespostaInvalida(f"achei {len(com_slides)} carrosséis na resposta; deixe só um")
    raise RespostaInvalida("não achei o JSON com \"slides\" na resposta. Copie a resposta inteira da IA, do { até o }")
