import { useState } from "react";

/* Panel de entrar / crear cuenta. Es el mismo formulario para los dos casos:
   sólo cambia a qué endpoint le pega y el texto de los botones. */
export default function Sesion({ onEntrar, onRegistrar, onCerrar }) {
  const [modo, setModo] = useState("login");
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const registrando = modo === "registro";

  async function enviar(e) {
    e.preventDefault();
    setError("");
    setOcupado(true);
    try {
      await (registrando ? onRegistrar : onEntrar)(usuario, clave);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="velo" onClick={onCerrar}>
      <form className="panel" onClick={(e) => e.stopPropagation()} onSubmit={enviar}>
        <h2>{registrando ? "Crear cuenta" : "Entrar"}</h2>

        <label>
          Usuario
          <input
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            autoComplete="username"
            autoFocus
          />
        </label>

        <label>
          Clave
          <input
            type="password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            autoComplete={registrando ? "new-password" : "current-password"}
          />
        </label>

        {error && <p className="panel-error">{error}</p>}

        <button className="panel-enviar" type="submit" disabled={ocupado}>
          {ocupado ? "Un momento…" : registrando ? "Crear cuenta" : "Entrar"}
        </button>

        <button
          type="button"
          className="panel-cambiar"
          onClick={() => { setModo(registrando ? "login" : "registro"); setError(""); }}
        >
          {registrando ? "Ya tengo cuenta" : "No tengo cuenta, quiero crear una"}
        </button>
      </form>
    </div>
  );
}
