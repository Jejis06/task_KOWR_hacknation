"""LLM w AgroLegal: wyjaśnia prostym językiem i odpowiada na pytania – NIE decyduje.

Ocena suszy, formalności, opłaty i statusy naborów pochodzą z reguł (blok `analysis`); LLM dostaje je jako kontekst
z ponumerowanymi źródłami, a linki i plakietki formalności dobieramy po stronie serwera (model nie może ich wymyślić).
Bez klucza / przy błędzie zwracamy teksty z szablonów (`source: "template"`).
"""
