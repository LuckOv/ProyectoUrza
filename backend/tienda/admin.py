from django.contrib import admin
from django.utils.html import format_html
from tienda.models import Inventario, Carrito, Pedido, PedidoItem, Movimiento, Descuento, Configuracion, Propuesta


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    readonly_fields = ("nombre", "set_nombre", "grado", "precio", "cantidad", "colores")


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = ("id", "mini_foto", "nombre", "set_nombre", "grado", "cantidad", "precio_usd", "legal_standard")
    list_filter = ("grado", "rareza", "legal_standard")
    search_fields = ("nombre", "set_nombre", "scryfall_id")
    ordering = ("nombre", "grado")

    def mini_foto(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="height: 40px; border-radius: 4px;" />', obj.imagen)
        return "-"
    mini_foto.short_description = "Carta"


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "apellido", "fecha_retiro", "hora_retiro", "total", "estado", "origen", "creado")
    list_filter = ("estado", "origen", "fecha_retiro")
    search_fields = ("nombre", "apellido", "thread_id")
    inlines = [PedidoItemInline]
    ordering = ("-id",)


@admin.register(Propuesta)
class PropuestaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "apellido", "email", "carta", "grado", "cantidad", "precio", "moneda", "estado")
    list_filter = ("estado", "moneda", "grado")
    search_fields = ("nombre", "apellido", "email", "carta")
    ordering = ("-id",)


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("id", "thread_id", "inventario", "cantidad", "agregado")
    search_fields = ("thread_id",)


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "tipo", "titulo", "unidades", "pedido_id")
    list_filter = ("tipo",)
    search_fields = ("titulo", "detalle")
    ordering = ("-id",)


@admin.register(Descuento)
class DescuentoAdmin(admin.ModelAdmin):
    list_display = ("id", "inventario", "porcentaje", "creado")


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ("clave", "valor_corto")
    search_fields = ("clave",)

    def valor_corto(self, obj):
        return (obj.valor[:80] + "...") if len(obj.valor) > 80 else obj.valor
    valor_corto.short_description = "Valor JSON"
