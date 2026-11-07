from django.db import models


class Inventario(models.Model):
    nombre = models.CharField(max_length=200)
    set_codigo = models.CharField(max_length=20, null=True, blank=True)
    set_nombre = models.CharField(max_length=200, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    rareza = models.CharField(max_length=50, null=True, blank=True)
    imagen = models.TextField(null=True, blank=True)
    scryfall_id = models.CharField(max_length=100, null=True, blank=True)
    grado = models.CharField(max_length=50, default="Sin graduar")
    precio_usd = models.FloatField(null=True, blank=True)
    cantidad = models.IntegerField(default=0)
    legal_standard = models.IntegerField(default=0)
    colores = models.CharField(max_length=20, null=True, blank=True)
    precio_mercado_usd = models.FloatField(null=True, blank=True)
    mercado_actualizado = models.CharField(max_length=50, null=True, blank=True)
    mercado_referencia_usd = models.FloatField(null=True, blank=True)
    precio_aceptado_usd = models.FloatField(null=True, blank=True)
    creado = models.CharField(max_length=50)
    actualizado = models.CharField(max_length=50)

    class Meta:
        db_table = "inventario"
        managed = False
        verbose_name = "Carta en Inventario"
        verbose_name_plural = "Inventario de Cartas"

    def __str__(self):
        return f"{self.nombre} ({self.set_nombre or 's/set'}) - {self.grado} [Stock: {self.cantidad}]"


class Carrito(models.Model):
    thread_id = models.CharField(max_length=100)
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE, db_column="inventario_id")
    cantidad = models.IntegerField(default=1)
    agregado = models.CharField(max_length=50)

    class Meta:
        db_table = "carrito"
        managed = False
        verbose_name = "Item de Carrito"
        verbose_name_plural = "Carritos Activos"

    def __str__(self):
        return f"Carrito {self.thread_id}: {self.cantidad}x {self.inventario.nombre}"


class Pedido(models.Model):
    thread_id = models.CharField(max_length=100, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_retiro = models.CharField(max_length=20)
    hora_retiro = models.CharField(max_length=10)
    total = models.FloatField()
    estado = models.CharField(max_length=50, default="pendiente")
    comentario = models.TextField(blank=True, default="")
    origen = models.CharField(max_length=50, default="chat")
    creado = models.CharField(max_length=50)
    actualizado = models.CharField(max_length=50)

    class Meta:
        db_table = "pedidos"
        managed = False
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.id} - {self.nombre} {self.apellido} (${self.total:,.0f}) [{self.estado}]"


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, db_column="pedido_id", related_name="items")
    inventario_id = models.IntegerField(null=True, blank=True)
    nombre = models.CharField(max_length=200)
    set_nombre = models.CharField(max_length=200, null=True, blank=True)
    set_codigo = models.CharField(max_length=20, null=True, blank=True)
    grado = models.CharField(max_length=50, null=True, blank=True)
    precio = models.FloatField(null=True, blank=True)
    cantidad = models.IntegerField()
    colores = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "pedido_items"
        managed = False
        verbose_name = "Item de Pedido"
        verbose_name_plural = "Items de Pedido"

    def __str__(self):
        return f"{self.cantidad}x {self.nombre} en Pedido #{self.pedido_id}"


class Movimiento(models.Model):
    fecha = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=200)
    detalle = models.TextField(blank=True, default="")
    unidades = models.IntegerField(default=0)
    pedido_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "movimientos"
        managed = False
        verbose_name = "Movimiento"
        verbose_name_plural = "Protocolo de Movimientos"

    def __str__(self):
        return f"[{self.fecha}] {self.tipo}: {self.titulo}"


class Descuento(models.Model):
    inventario = models.OneToOneField(Inventario, on_delete=models.CASCADE, db_column="inventario_id")
    porcentaje = models.FloatField()
    creado = models.CharField(max_length=50)

    class Meta:
        db_table = "descuentos"
        managed = False
        verbose_name = "Descuento"
        verbose_name_plural = "Descuentos por Carta"

    def __str__(self):
        return f"{self.porcentaje}% en {self.inventario.nombre}"


class Configuracion(models.Model):
    clave = models.CharField(max_length=100, primary_key=True)
    valor = models.TextField()

    class Meta:
        db_table = "config"
        managed = False
        verbose_name = "Configuración"
        verbose_name_plural = "Configuraciones Dinámicas"

    def __str__(self):
        return self.clave


class Propuesta(models.Model):
    thread_id = models.CharField(max_length=100, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(max_length=200)
    carta = models.CharField(max_length=200)
    scryfall_id = models.CharField(max_length=100, null=True, blank=True)
    set_nombre = models.CharField(max_length=200, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    imagen = models.TextField(null=True, blank=True)
    grado = models.CharField(max_length=50)
    cantidad = models.IntegerField(default=1)
    precio = models.FloatField()
    moneda = models.CharField(max_length=10, default="ARS")
    comentario_cliente = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=50, default="nueva")
    comentario_vendedor = models.TextField(blank=True, default="")
    cargada = models.IntegerField(default=0)
    creado = models.CharField(max_length=50)
    actualizado = models.CharField(max_length=50)

    class Meta:
        db_table = "propuestas"
        managed = False
        verbose_name = "Propuesta de Carta"
        verbose_name_plural = "Propuestas de Clientes"

    def __str__(self):
        return f"Propuesta #{self.id} de {self.nombre} {self.apellido}: {self.carta} ({self.estado})"
