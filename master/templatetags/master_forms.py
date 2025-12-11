from django import template

register = template.Library()


@register.filter
def widget_attr(field, attr_name):
    """
    Safely fetch a widget attribute from a bound field.

    Usage:
        {{ field|widget_attr:"data-span" }}
    """
    if not hasattr(field, "field"):
        return ""
    widget = getattr(field.field, "widget", None)
    if not widget:
        return ""
    attrs = getattr(widget, "attrs", {})
    return attrs.get(attr_name, "")
