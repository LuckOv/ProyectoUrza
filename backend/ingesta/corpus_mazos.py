"""Corpus de conocimiento curado para el RAG de Mazos (Saheeli).

Contiene artículos técnicos y guías de construcción sobre:
- Arquetipos fundamentales (Aggro, Midrange, Control, Combo, Tribal, Sacrificio).
- Matemáticas de maná y bases de maná (Fórmulas Karsten, tierras requeridas).
- Teoría de la curva de maná y ratios de interacción.
- Estructura de mazos para formatos Construidos (Standard, Pioneer, Modern) y Commander.
- Metodología de análisis y mejora de mazos (Upgrades, cortes y adiciones).
"""

DOCUMENTOS_MAZOS = [
    {
        "id": "teoria_curva_mana",
        "titulo": "Teoría de la Curva de Maná y Distribución de Costes",
        "categoria": "fundamentos",
        "formato": "general",
        "contenido": """
La curva de maná (Mana Curve) es la columna vertebral de cualquier mazo competitivo de Magic: The Gathering.
Determina la probabilidad matemática de aprovechar eficientemente todo el maná disponible en cada turno.

1. Reglas por tipo de estrategia:
- Mazos Agresivos (Aggro / Burn): Pico masivo en costes 1 y 2. Distribución típica en 60 cartas:
  * Coste 1: 8 a 14 cartas (criaturas con prisa o poder 2+, chispas de 1 maná).
  * Coste 2: 10 a 14 cartas (amenazas clave o multiplicadores de daño).
  * Coste 3: 4 a 8 cartas (remates o motores de ventaja rápidos).
  * Coste 4 o más: 0 a 3 cartas como máximo absoluto.
  * Tierras: 20 a 22 tierras.

- Mazos de Rango Medio (Midrange): Curva suave y equilibrada. Pico en costes 2 y 3:
  * Coste 1: 4 a 8 cartas (descarte selectivo, remoción barata o aceleradores).
  * Coste 2: 8 a 12 cartas (criaturas eficientes 2-por-1, interacción premium).
  * Coste 3: 8 a 10 cartas (amenazas resilientes que generan ventaja si no se responden).
  * Coste 4-5: 4 a 6 cartas (bombas que cierran la partida o barren la mesa).
  * Tierras: 24 a 25 tierras.

- Mazos de Control: Curva defensiva reactiva:
  * Coste 1-2: 8 a 12 cartas (remoción puntual barata, cantrips, contrachispas de 2 manás).
  * Coste 3-4: 8 a 10 cartas (contrahechizos incondicionales, motores de robo a velocidad de instantáneo, barredores de mesa como Day of Judgment, Sunfall o Wrath of God).
  * Coste 5+: 4 a 6 cartas (finishers difíciles de responder, planeswalkers dominantes).
  * Tierras: 25 a 27 tierras.

2. Diagnóstico de errores comunes de curva:
- 'Curva pesada': Más de 10 cartas de coste 4 o superior sin aceleración de maná. Provoca partidas perdidas con cartas atascadas en la mano.
- Falta de interactividad en turnos 1 y 2: Un mazo sin jugadas en los primeros dos turnos pierde inevitablemente contra arquetipos agresivos o tempo.
"""
    },
    {
        "id": "teoria_base_mana",
        "titulo": "Cálculo de Bases de Maná y Fuentes de Color (Método Karsten)",
        "categoria": "fundamentos",
        "formato": "general",
        "contenido": """
La base de maná determina si vas a poder lanzar tus cartas en tiempo y forma.
Según los cálculos de Frank Karsten (90% de probabilidad de tener el color en el turno adecuado en un mazo de 60 cartas):

1. Fuentes mínimas de un color según el coste:
- Para jugar un hechizo de coste 1 (ejemplo: {R} o {G} en Turno 1 como Llanowar Elves): Necesitás mínimo 14 fuentes de ese color.
- Para jugar un coste 2 de color simple (ejemplo: {1}{B} en Turno 2): Necesitás 13 fuentes.
- Para jugar un coste 2 de doble color (ejemplo: {B}{B} o {R}{R} en Turno 2): Necesitás mínimo 19 a 20 fuentes de ese color.
- Para un coste 3 de color simple ({2}{U}): Necesitás 11 a 12 fuentes.
- Para un coste 3 de doble color ({1}{W}{W}): Necesitás 17 a 18 fuentes.
- Para un coste 4 de doble color ({2}{U}{U}): Necesitás 16 fuentes.

2. Selección de Tierras:
- Tierras que entran enderezadas (Fastlands, Painlands, Shocklands): Cruciales para mazos Aggro y Midrange. Un mazo agresivo no puede permitirse más de 0 a 2 tierras giradas.
- Tierras de utilidad: Tierras como Cavern of Souls son vitales en mazos tribales porque corrigen cualquier combinación de colores para el tipo elegido y hacen que las criaturas sean incontables.
- Tierras dobles con ciclo o condición (Checklands, Triomas, Surveil lands): Ideales para control y midrange de 3 colores, aportan valor en juego tardío.
"""
    },
    {
        "id": "arquetipo_mono_red_aggro",
        "titulo": "Arquetipo Mono Red Aggro / Prowess / Burn",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_modern",
        "contenido": """
El arquetipo Mono Red (o Rakdos/Gruul Aggro) tiene como objetivo reducir las vidas del oponente a 0 entre los turnos 3 y 5.

1. Filosofía de juego:
Cada carta debe representar daño directo o potencial de daño inmediato. Las criaturas deben tener prisa (haste) o habilidades como Prowess / Valiant que escalen con hechizos baratos.

2. Piezas Fundamentales:
- Drop 1 (Amenazas rápidas): Heartfire Hero, Monastery Swiftspear, Kumano Faces Kakkazan.
- Drop 2 (Motores de daño): Slickshot Show-Off, Emberheart Challenger, Manifold Mouse.
- Hechizos de soporte / Bombeo: Monstrous Rage, Might of the Meek, Giant Growth o efectos similares que otorguen evasión (arrollar/trample).
- Chispas de remoción / Daño directo: Lightning Bolt, Play with Fire, Shock, Abrade para limpiar bloqueadores o rematar al rival a la cara.

3. Base de maná:
- 19 a 21 tierras, casi exclusivamente montañas y tierras utilitarias rojas enderezadas.
- Sinergias en la tienda URZA: Heartfire Hero combinado con hechizos de objetivo para infligir daño letal al morir.
"""
    },
    {
        "id": "arquetipo_midrange_negro_verde",
        "titulo": "Arquetipos Midrange: Golgari, Dimir y Jund",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_modern",
        "contenido": """
El arquetipo Midrange se basa en el principio de 'ventaja de cartas' y 'calidad individual de amenazas' (card quality).
No busca ganar rápido como Aggro, ni aguantar indefinidamente como Control, sino dejar sin recursos al rival y ganar con amenazas superiores.

1. Composición de la plantilla Midrange (60 cartas):
- Interrupción y Descarte (6-8 slots): Deep-Cavern Bat, Duress, Thoughtseize, Liliana of the Veil. Extraen la respuesta clave del rival y dan información de su mano.
- Remoción Eficiente (8-10 slots): Cut Down, Go for the Throat, Bitter Triumph, Tear Asunder, Assassin's Trophy, Get Lost.
- Criaturas y Amenazas 2-por-1 (14-18 slots): Criaturas que al entrar o al atacar generan valor o roban cartas (ej. Preacher of the Schism, Glissa Sunslayer, Mosswood Dreadknight).
- Ventaja y Motores de Robo (4-6 slots): Enduring Innocence, Phyrexian Arena o planeswalkers.
- Base de maná: 24 a 25 tierras balanceadas.

2. Cómo mejorar un mazo Midrange:
- Si pierde contra Aggro: Reducir costes altos y sumar remoción barata a velocidad de instantáneo de 1 y 2 manás (Cut Down, Go for the Throat) o criaturas con Lifelink.
- Si pierde contra Control: Sumar más descarte (Deep-Cavern Bat), amenazas difíciles de contrarrestar (Cavern of Souls) o permanentes resistentes a barredores.
"""
    },
    {
        "id": "arquetipo_tribal_elfos",
        "titulo": "Arquetipo Tribal de Elfos (Mono Green / Golgari Elves)",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_modern_commander",
        "contenido": """
El mazo de Elfos es un clásico arquetipo de rampa explosiva y efecto 'bola de nieve' (go-wide ramp).

1. Estructura del mazo:
- Generadores de maná Turno 1 (Mana Dorks): Llanowar Elves, Elvish Mystic, Fyndhorn Elves. Permitir saltar de turno 1 a turno 3 de maná de forma consistente.
- Señores y Aumentadores de Fuerza (Lords): Leaf-Crowned Visionary, Elvish Archdruid, Dwynen's Elite. Convierten a una horda de criaturas 1/1 en amenazas 3/3 o mayores.
- Motores de Robo y ventaja: Leaf-Crowned Visionary, Beast Whisperer. Cada elfo jugado roba otro elfo, vaciando la biblioteca en el campo.
- Finisher masivo: Cartas que otorguen Arrollar y +X/+X como Craterhoof Behemoth, Ezuri, Renegade Leader o Overwhelming Stampede.

2. Pieza clave de la tienda:
- Cavern of Souls: Imprescindible para el mazo. Nombra 'Elfo', permite fijar cualquier color de maná para elfos multiclase (como Golgari o Simic) y neutraliza completamente los mazos de control con contrahechizos.
- Llanowar Elves: La base angular de cualquier mazo verde con presencia en la tienda.
"""
    },
    {
        "id": "arquetipo_control_blanco_azul",
        "titulo": "Arquetipo Control: Azorius y Esper Control",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_modern",
        "contenido": """
El arquetipo de Control juega a desgastar todas las amenazas del rival hasta que este se quede sin cartas, para luego ganar la partida con una amenaza dominante o planeswalker.

1. Plantilla de Control (60 cartas):
- Barredores de mesa masivos (Board Wipes, 4-6 slots): Sunfall, Day of Judgment, Wrath of God, Temporary Lockdown, Supreme Verdict.
- Contrachispas / Permiso (6-8 slots): No More Lies, Make Disappear, Counterspell, Negate, Dovin's Veto.
- Remoción puntual versátil (6-8 slots): Get Lost, The Wandering Emperor, March of Otherworldly Light, Leyline Binding.
- Motores de ventaja de cartas (4-6 slots): Memory Deluge, Deduce, Teferi, planeswalkers.
- Condición de victoria (2-3 slots): Criaturas con protección o planeswalkers que cierren el juego.
- Tierras: 26 a 27 tierras (imprescindible nunca perder un land drop en los primeros 6 turnos).

2. Consejos para jugar y armar Control:
- No gastar remoción puntual en criaturas pequeñas si vas a tirar un barredor de mesa en turno 4.
- El 80% de tus hechizos deben poder jugarse en el turno del oponente (velocidad de Instantáneo) para mantener maná abierto para contrahechizo o robo.
"""
    },
    {
        "id": "arquetipo_sacrificio_aristocrats",
        "titulo": "Arquetipo Aristocrats y Sacrificio (Black-White / Rakdos)",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_commander",
        "contenido": """
El arquetipo Aristocrats basa su plan de juego en el valor acumulado de sacrificar sus propias criaturas y permanentes para drenar vidas y generar ventaja.

1. Los 3 componentes necesarios:
- Generadores de 'alimento' (Fodder): Criaturas que al morir dejan fichas o vuelven del cementerio, fichas de criatura baratas.
- Salidas de sacrificio (Sacrifice Outlets): Efectos que permitan sacrificar permanentes a cambio de maná, contadores, robo o daño.
- Castigadores / Drenadores (Payoffs / Drainers): Cartas que hacen que el oponente pierda vidas o tú ganes vidas cada vez que una criatura propia muere (ej. Bloodthirsty Conqueror, Blood Artist, Zulaport Cutthroat, Elas il-Kor).

2. Sinergias clave de la tienda URZA:
- Bloodthirsty Conqueror: Si el oponente pierde vida, ganas esa vida; si ganas vida, dispara sinergias masivas. Pieza estelar para mazos negros de drenaje.
- Enduring Innocence: Garantiza robar carta cada vez que entra una criatura pequeña, manteniendo la mano llena en turnos clave.
"""
    },
    {
        "id": "estructura_commander_edh",
        "titulo": "Estructura y Ratios Recomendados para Mazos de Commander (EDH)",
        "categoria": "commander",
        "formato": "commander",
        "contenido": """
Construcción de un mazo de Commander (100 cartas singleton):

1. Ratios estándar de construcción (Regla 8x8 o balance clásico):
- Tierras: 36 a 38 tierras (reducir a 34-35 sólo si el coste medio de maná es menor a 2.5).
- Aceleración de maná (Ramp): 10 a 12 cartas de coste 2 o menor (Sol Ring, Arcane Signet, Llanowar Elves, Talismanes, Sellos, Farseek, Cultivate).
- Motores de Robo / Ventaja de cartas: 10 a 12 cartas (motores continuos como Beast Whisperer, Rhystic Study, Phyrexian Arena o robos masivos).
- Remoción puntual interactiva: 10 a 12 cartas (mínimo 5 que respondan a criaturas y 5 que respondan a artefactos/encantamientos a velocidad de instantáneo).
- Barredores de mesa (Board Wipes): 2 a 4 cartas para resetear la partida en caso de desventaja.
- Sinergias y Plan del Comandante: 30 a 35 cartas dedicadas al plan de juego específico.

2. Errores habituales en Commander:
- Jugar menos de 35 tierras y menos de 8 piezas de rampa: genera partidas donde el jugador queda estancado en 3 manás mirando jugar a los demás.
- No incluir suficiente interacción a velocidad de instantáneo: permite que los combos de otros jugadores se resuelvan sin oposición.
"""
    },
    {
        "id": "metodologia_mejora_mazos",
        "titulo": "Metodología de Saheeli para Evaluar y Mejorar un Mazo",
        "categoria": "mejora",
        "formato": "general",
        "contenido": """
Cuando un jugador presenta su lista de mazo actual para pedir mejoras, Saheeli sigue un proceso estructurado en 4 pasos:

Paso 1: Identificación del Núcleo y Condición de Victoria:
¿Cuál es la forma principal en que este mazo gana la partida? (¿ataque masivo de fichas, daño directo, combo, drenaje de vidas, control?).
Cualquier carta que no contribuya directamente a esta condición de victoria o a protegerla es candidata a ser retirada.

Paso 2: Auditoría de la Curva de Maná y la Base de Maná:
- Contar el número de tierras: ¿está dentro del rango recomendado para su arquetipo?
- Analizar los costes de maná: ¿hay un cuello de botella en coste 3 o 4? ¿faltan jugadas en turno 1 y 2?

Paso 3: Diagnóstico de Cortes (Cuts):
- Cartas 'trampa' o demasiado situacionales (Win-more cards que solo sirven cuando ya vas ganando).
- Cartas de coste muy elevado sin impacto inmediato en la mesa.
- Cartas fuera de sinergia con el resto del mazo.

Paso 4: Sugerencias de Adición (Adds) priorizando el Inventario:
- Recomendar cartas específicas disponibles en el catálogo de la tienda para cubrir las carencias identificadas (mejor base de maná con tierras como Cavern of Souls, remoción premium, o aceleradores como Llanowar Elves).
- Justificar en una oración qué carta sale y por qué la carta recomendada mejora la consistencia del mazo.
"""
    },
    {
        "id": "regla_estricta_identidad_color",
        "titulo": "Regla Estricta de Identidad de Color, Gremios y Compatibilidad de Maná",
        "categoria": "fundamentos",
        "formato": "general",
        "contenido": """
En Magic: The Gathering, la regla de oro absoluta en la construcción y mejora de un mazo es el RESPETO ESTRICTO A LA IDENTIDAD DE COLOR.

1. Regla de compatibilidad y legalidad:
- Un mazo solo puede castear y jugar de forma consistente cartas de sus propios colores o cartas incoloras (tierras y artefactos sin requerimiento de maná de color ajeno).
- En formatos como Commander / Brawl, las cartas que no compartan la identidad de color del comandante son DIRECTAMENTE ILEGALES.
- En formatos construidos (Standard, Pioneer, Modern), agregar cartas de un tercer o cuarto color ajeno a la base de maná sin el soporte adecuado arruina la probabilidad matemática de Karsten y vuelve la carta un 'peso muerto' incasteable en mano.
- JAMÁS sugieras una carta cuyos colores choquen con el mazo pedido. Por ejemplo:
  * Si el mazo es Rojo-Verde (Gruul / RG): NUNCA sugieras cartas blancas, azules o negras (como No More Lies, Day of Judgment o Thoughtseize). El hecho de que la tienda tenga stock de No More Lies NO justifica sugerirla para un mazo rojo-verde.
  * Si el mazo es Blanco-Azul (Azorius / WU): NUNCA sugieras cartas rojas, verdes o negras.
  * Si el mazo es Mono Verde (G): SOLO sugerí cartas verdes o incoloras (Llanowar Elves, Cavern of Souls).

2. Clasificación de Gremios (2 colores) y Clanes/Fragmentos:
- Azorius (WU): Blanco-Azul (Control, permiso, No More Lies).
- Dimir (UB): Azul-Negro (Control, descarte, robo).
- Rakdos (BR): Negro-Rojo (Agro, daño, sacrificio, Bloodthirsty Conqueror).
- Gruul (RG): Rojo-Verde (Agro feroz, bichos grandes, pisotón, Llanowar Elves, Heartfire Hero, Slickshot Show-Off).
- Selesnya (GW): Verde-Blanco (Fichas, contadores, Enduring Innocence).
- Orzhov (WB): Blanco-Negro (Aristócratas, drenaje).
- Izzet (UR): Azul-Rojo (Hechizos rápidos, prowess, tempo).
- Golgari (BG): Negro-Verde (Midrange, cementerio, Mosswood Dreadknight).
- Boros (WR): Blanco-Rojo (Agro veloz, equipamiento, criaturas con prisa).
- Simic (UG): Verde-Azul (Rampa, criaturas gigantes, ventaja de cartas).
- Fragmentos / Clanes: Jund (BRG), Naya (WRG), Esper (WUB), Grixis (UBR), Bant (GWU), Abzan (WBG), Jeskai (URW), Sultai (UBG), Mardu (WBR), Temur (URG).

3. Compatibilidad de cartas incoloras:
- Tierras utilitarias como Cavern of Souls o Three Tree City, y artefactos sin coste de color ajeno son compatibles con CUALQUIER mazo y deben ser recomendadas para fortalecer la base de maná o la sinergia tribal.
"""
    },
    {
        "id": "arquetipo_gruul_aggro_stompy",
        "titulo": "Arquetipo Gruul (Rojo-Verde / RG): Aggro, Stompy y Prowess",
        "categoria": "arquetipos",
        "formato": "standard_pioneer_modern",
        "contenido": """
El arquetipo Gruul combina la aceleración y tamaño del color verde ({G}) con la velocidad, daño directo y prisa del color rojo ({R}).

1. Plan de juego Gruul:
- Turno 1: Generador de maná verde (Llanowar Elves) para acelerar a coste 3 en Turno 2, o drop agresivo rojo (Heartfire Hero).
- Turno 2: Amenazas con prisa o multiplicadores de daño (Slickshot Show-Off, Manifold Mouse) o bichos resilientes.
- Turno 3-4: Permanentes masivos verdes con arrollar (Overlord of the Hauntwoods) y trucos de combate de bombeo.
- Remoción: Chispas directas rojas (Lightning Bolt, Abrade, Shock) y peleas verdes (Bite Down).

2. Cartas clave disponibles en el inventario URZA:
- Llanowar Elves: Motor verde de aceleración T1 fundamental.
- Heartfire Hero: Drop 1 rojo hiperagresivo con Valiant y daño letal al morir.
- Slickshot Show-Off: Amenaza voladora roja con Prowess y Plot.
- Overlord of the Hauntwoods: Generador de tierras y presencia gigante verde.
- Cavern of Souls: Corrige el maná para nombrar guerrero, chamán o bestia y asegura que los atacantes no sean contrarrestados.

3. Cartas prohibidas en Gruul:
- Ninguna carta con coste {W}, {U} o {B} (como No More Lies, Deep-Cavern Bat o Enduring Innocence) debe ser incluida en una lista Gruul.
"""
    }
]
