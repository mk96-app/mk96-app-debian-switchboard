"""Lógica pura de agrupación del menú de bandeja: qué módulos van juntos en cada submenú
y cómo se rotula cada submenú (icono + nombre + resumen del estado actual)."""

GROUP_ICONS = {
    "Audio": "🔊",
    "Pantalla": "🖥",
    "Energía": "⚡",
    "Conectividad": "📶",
}


def group_modules(modules) -> list:
    """Agrupa módulos por su atributo `group`, respetando el orden de primera aparición.
    Devuelve [(nombre_grupo, [módulos])]."""
    groups = {}
    for module in modules:
        groups.setdefault(module.group, []).append(module)
    return list(groups.items())


def format_group_label(group: str, summaries) -> str:
    """Etiqueta del submenú: '🔊 Audio · 65%'. Los resúmenes vacíos/None se ignoran."""
    icon = GROUP_ICONS.get(group)
    label = f"{icon} {group}" if icon else group
    parts = [s for s in summaries if s]
    return f"{label} · {', '.join(parts)}" if parts else label
