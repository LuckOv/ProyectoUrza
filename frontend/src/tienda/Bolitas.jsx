import { useEffect, useRef } from "react";

/* Las bolitas son recortes del dorso de la carta, no dibujos: conservan
   tal cual las luces, las sombras y el color originales. Van en el orden
   horario del dorso, empezando arriba. */
const SPRITES = [
  "/mana-blanco.png",
  "/mana-azul.png",
  "/mana-negro.png",
  "/mana-rojo.png",
  "/mana-verde.png",
];

const SEPARACION = 34;     // distancia entre bolita y bolita cuando persigue
const RADIO_ORBITA = 34;   // radio del pentágono cuando está quieto
const QUIETO_MS = 300;     // cuánto espera antes de ponerse a girar
const RADIO = 6;          // mitad del tamaño con que se dibuja cada bolita

/* El puntero real es la punta de la flecha, pero el dibujo se extiende hacia
   abajo y a la derecha desde ahí. Si centramos el anillo en la punta, la
   flecha queda corrida adentro. Este corrimiento lo centra sobre el cuerpo. */
const CENTRO_FLECHA = { x: 9, y: 11 };

export default function Bolitas() {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    let listas = false;
    const imagenes = SPRITES.map((ruta) => {
      const img = new Image();
      img.src = ruta;
      return img;
    });
    Promise.all(
      imagenes.map((img) =>
        img.decode().catch(() => new Promise((r) => { img.onload = r; img.onerror = r; }))
      )
    ).then(() => { listas = true; });

    let ancho = 0, alto = 0;
    const ajustar = () => {
      const dpr = window.devicePixelRatio || 1;
      ancho = window.innerWidth;
      alto = window.innerHeight;
      canvas.width = ancho * dpr;
      canvas.height = alto * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    ajustar();
    window.addEventListener("resize", ajustar);

    const bolitas = SPRITES.map(() => ({ x: -60, y: alto / 2 }));

    let raton = { x: ancho / 2, y: alto / 2 };
    let ancla = { ...raton };
    let ultimoMovimiento = 0;
    let angulo = -Math.PI / 2;
    let visible = false;
    let girando = false;
    // Hacia dónde venía yendo el mouse. Decide en qué punta del pentágono
    // queda la cabeza al frenar, para que el armado siga el movimiento.
    let direccion = { x: 1, y: 0 };

    const alMover = (e) => {
      const dx = e.clientX - raton.x;
      const dy = e.clientY - raton.y;
      const largo = Math.hypot(dx, dy);
      if (largo > 1) {
        direccion.x += (dx / largo - direccion.x) * 0.25;
        direccion.y += (dy / largo - direccion.y) * 0.25;
      }
      raton = { x: e.clientX, y: e.clientY };
      ancla = { ...raton };
      ultimoMovimiento = performance.now();
      visible = true;
    };
    const alSalir = () => { visible = false; };
    window.addEventListener("pointermove", alMover);
    window.addEventListener("pointerdown", alMover);
    document.addEventListener("pointerleave", alSalir);

    let anterior = performance.now();
    let animacion;

    const cuadro = (ahora) => {
      const dt = Math.min((ahora - anterior) / 1000, 0.05);
      anterior = ahora;
      const quieto = ahora - ultimoMovimiento > QUIETO_MS;

      if (quieto) {
        // La cabeza se queda mirando hacia donde venía el mouse y las demás
        // se reparten hacia atrás por el anillo, respetando el orden de la
        // cadena. Así se abren en abanico en vez de juntarse en el centro.
        if (!girando) {
          angulo = Math.atan2(direccion.y, direccion.x);
          girando = true;
        }
        angulo += dt * 1.1;
        const paso = (Math.PI * 2) / bolitas.length;
        const acomodar = 1 - Math.pow(0.02, dt);
        const cx = ancla.x + CENTRO_FLECHA.x;
        const cy = ancla.y + CENTRO_FLECHA.y;
        bolitas.forEach((b, i) => {
          const a = angulo + i * paso;
          b.x += (cx + Math.cos(a) * RADIO_ORBITA - b.x) * acomodar;
          b.y += (cy + Math.sin(a) * RADIO_ORBITA - b.y) * acomodar;
        });
      } else {
        girando = false;
        // Cuanto más chico este número, más pegada va la cabeza al cursor.
        const suave = 1 - Math.pow(0.00002, dt);
        const cabeza = bolitas[0];
        cabeza.x += (raton.x - cabeza.x) * suave;
        cabeza.y += (raton.y - cabeza.y) * suave;

        for (let i = 1; i < bolitas.length; i++) {
          const previa = bolitas[i - 1], actual = bolitas[i];
          const dx = actual.x - previa.x, dy = actual.y - previa.y;
          const dist = Math.hypot(dx, dy) || 0.0001;
          actual.x = previa.x + (dx / dist) * SEPARACION;
          actual.y = previa.y + (dy / dist) * SEPARACION;
        }
      }

      ctx.clearRect(0, 0, ancho, alto);

      if (visible && listas) {
        ctx.shadowColor = "rgba(18, 9, 3, 0.45)";
        ctx.shadowBlur = 6;
        ctx.shadowOffsetY = 2;
        for (let i = bolitas.length - 1; i >= 0; i--) {
          ctx.drawImage(imagenes[i], bolitas[i].x - RADIO, bolitas[i].y - RADIO, RADIO * 2, RADIO * 2);
        }
        ctx.shadowColor = "transparent";
        ctx.shadowBlur = 0;
        ctx.shadowOffsetY = 0;
      }

      animacion = requestAnimationFrame(cuadro);
    };
    animacion = requestAnimationFrame(cuadro);

    return () => {
      cancelAnimationFrame(animacion);
      window.removeEventListener("resize", ajustar);
      window.removeEventListener("pointermove", alMover);
      window.removeEventListener("pointerdown", alMover);
      document.removeEventListener("pointerleave", alSalir);
    };
  }, []);

  return <canvas className="bolitas" ref={canvasRef} aria-hidden="true" />;
}
