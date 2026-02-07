from django import template

register = template.Library()

@register.filter(name='multiply')
def multiply(value, arg):
    """Умножает значение на аргумент"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='divide')
def divide(value, arg):
    """Делит значение на аргумент"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0