"""Reportes ejecutivos de la tienda para el dueño vía Telegram móvil."""

from datetime import datetime, timedelta
from tienda import base, inventario, tienda


def resumen_ventas() -> str:
    """Genera un resumen de facturación y pedidos para el dueño."""
    pedidos = tienda.listar_pedidos()
    hoy_str = base.ahora().date().isoformat()
    hace_7_dias = (base.ahora() - timedelta(days=7)).date().isoformat()
    hace_30_dias = (base.ahora() - timedelta(days=30)).date().isoformat()

    ventas_hoy = [p for p in pedidos if p.get("creado", "").startswith(hoy_str) and p.get("estado") != "rechazado"]
    ventas_7d = [p for p in pedidos if p.get("creado", "")[:10] >= hace_7_dias and p.get("estado") != "rechazado"]
    ventas_30d = [p for p in pedidos if p.get("creado", "")[:10] >= hace_30_dias and p.get("estado") != "rechazado"]

    total_hoy = sum(p.get("total", 0) for p in ventas_hoy)
    total_7d = sum(p.get("total", 0) for p in ventas_7d)
    total_30d = sum(p.get("total", 0) for p in ventas_30d)

    pendientes = [p for p in pedidos if p.get("estado") == "pendiente"]

    return (
        "📊 *REPORTE DE VENTAS - TIENDA URZA*\n\n"
        f"• *Hoy:* {len(ventas_hoy)} pedidos — *${total_hoy:,.0f} ARS*\n"
        f"• *Últimos 7 días:* {len(ventas_7d)} pedidos — *${total_7d:,.0f} ARS*\n"
        f"• *Últimos 30 días:* {len(ventas_30d)} pedidos — *${total_30d:,.0f} ARS*\n\n"
        f"⏳ *Pedidos pendientes de retiro:* {len(pendientes)}"
    )


def resumen_pedidos_pendientes() -> str:
    """Detalla los pedidos pendientes ordenados por fecha de retiro."""
    pedidos = tienda.listar_pedidos(estado="pendiente")
    if not pedidos:
        return "✅ *No hay pedidos pendientes de retiro.* Todos fueron entregados o no hay nuevos."

    lineas = ["⏳ *PEDIDOS PENDIENTES DE RETIRO:*\n"]
    for p in pedidos[:10]:
        lineas.append(
            f"• *#{p['id']}* — {p['nombre']} {p['apellido']}\n"
            f"  📅 Retiro: {p['fecha_retiro']} {p['hora_retiro']} hs\n"
            f"  💰 Total: ${p['total']:,.0f} ({p['unidades']} cartas)"
        )

    if len(pedidos) > 10:
        lineas.append(f"\n_... y {len(pedidos) - 10} pedidos más en Mesa Central._")

    return "\n".join(lineas)


def resumen_alertas() -> str:
    """Lista cartas con stock bajo o precios desfasados con el mercado."""
    items = inventario.listar()
    stock_bajo = [i for i in items if i.get("estado_stock") == "bajo"]
    sin_stock = [i for i in items if i.get("estado_stock") == "sin_stock"]
    alertas_precio = [i for i in items if i.get("alerta_precio")]

    lineas = ["⚠️ *ALERTAS DE INVENTARIO:*\n"]

    if stock_bajo:
        lineas.append(f"📉 *Stock bajo ({len(stock_bajo)} cartas):*")
        for i in stock_bajo[:5]:
            lineas.append(f"  • {i['nombre']} ({i['grado']}): solo {i['cantidad']} u.")
        if len(stock_bajo) > 5:
            lineas.append(f"  _...y {len(stock_bajo) - 5} más._")
        lineas.append("")

    if sin_stock:
        lineas.append(f"❌ *Agotadas ({len(sin_stock)} cartas):*")
        for i in sin_stock[:5]:
            lineas.append(f"  • {i['nombre']} ({i['grado']})")
        if len(sin_stock) > 5:
            lineas.append(f"  _...y {len(sin_stock) - 5} más._")
        lineas.append("")

    if alertas_precio:
        lineas.append(f"💲 *Alertas de precio ({len(alertas_precio)} cartas):*")
        for i in alertas_precio[:5]:
            lineas.append(f"  • {i['nombre']} ({i['grado']}): tu precio US${i.get('precio_usd', 0):.2f} vs mercado US${i.get('mercado_hoy_usd', 0):.2f}")
        if len(alertas_precio) > 5:
            lineas.append(f"  _...y {len(alertas_precio) - 5} más._")
        lineas.append("")

    if not stock_bajo and not sin_stock and not alertas_precio:
        return "✅ *Inventario en orden:* No hay alertas de stock bajo ni desfasajes de precio."

    return "\n".join(lineas)
