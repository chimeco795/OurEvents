from django import template
register = template.Library()

@register.filter
def estrellas(valor):
    numero = min(5, max(0, int(float(valor or 0) + 0.5)))
    return '★' * numero + '☆' * (5 - numero)
