#!/usr/bin/env python3
"""build_todo.py - genera web/index.html a partir de los TODO.md del proyecto.

Los .md mandan y el HTML se genera. index.html NUNCA se edita a mano.

Uso:
    python web/build_todo.py

Lee TODO.md de la raiz (pestana general) y subproyectos/*/TODO.md (una pestana
cada uno). Si un .md no parsea, avisa aqui y no en la pagina.

Formato que espera, contrato con el CLAUDE.md raiz:

    ## [slug] Titulo de la pestana

    Parrafo de contexto, opcional. Sale encima de la lista.

    ### Fase 0 - Agrupacion         (opcional)

    - [x] REF-1 - Titulo corto (2026-07-26)
          > Detalle opcional. Las lineas se unen en un parrafo.
          >
          > Una linea vacia abre parrafo nuevo.
          > - Una linea que empieza por el punto medio es una vineta,
          >   y se continua indentando dos espacios.
          > Artefacto: `ruta/al/archivo.md`
"""

import html
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "web" / "index.html"

# Orden de las pestanas. Lo que no este aqui va al final, alfabetico.
ORDEN = ["referencias", "asesor", "perfil", "transporte_optimo", "infra"]

# La pestana general se renombra: en el .md el slug es tecnico, en la web no.
ETIQUETAS = {"infra": "General"}

RE_SECCION = re.compile(r"^##\s+\[([^\]]+)\]\s+(.*)$")
RE_GRUPO = re.compile(r"^###\s+(.*)$")
RE_TAREA = re.compile(
    r"^-\s+\[([ xX])\]\s+\*{0,2}([A-Za-z]+-\d+[a-z]?)\*{0,2}\s*[—–-]\s*(.*)$"
)
RE_DETALLE = re.compile(r"^\s*>\s?(.*)$")
RE_FECHA = re.compile(r"\s*\((\d{4}-\d{2}-\d{2})\)\s*$")
RE_ARTEFACTO = re.compile(r"^Artefactos?\s*:", re.IGNORECASE)

RE_CODIGO = re.compile(r"`([^`]+)`")
RE_MATE = re.compile(r"\$([^$]+)\$")
RE_ENLACE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_FUERTE = re.compile(r"\*\*([^*]+)\*\*")
RE_ENFASIS = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")

MARCAS = {"\U0001f534": "alerta", "⚠️": "aviso", "✅": "hecho"}


# ---------------------------------------------------------------- inline

def inline(texto):
    """Markdown de linea a HTML. Protege codigo y matematicas primero."""
    guardados = []

    def guardar(fragmento):
        guardados.append(fragmento)
        return "\x00%d\x00" % (len(guardados) - 1)

    texto = RE_CODIGO.sub(
        lambda m: guardar("<code>%s</code>" % html.escape(m.group(1))), texto
    )
    # La matematica se deja literal para que MathJax la procese si hay red.
    texto = RE_MATE.sub(
        lambda m: guardar(
            '<span class="mate">$%s$</span>' % html.escape(m.group(1))
        ),
        texto,
    )

    texto = html.escape(texto)
    texto = RE_ENLACE.sub(
        lambda m: guardar(
            '<a href="%s" target="_blank" rel="noopener">%s</a>'
            % (m.group(2), m.group(1))
        ),
        texto,
    )
    texto = RE_FUERTE.sub(r"<strong>\1</strong>", texto)
    texto = RE_ENFASIS.sub(r"<em>\1</em>", texto)

    for i, fragmento in enumerate(guardados):
        texto = texto.replace("\x00%d\x00" % i, fragmento)
    return texto


def clase_marca(texto):
    for emoji, clase in MARCAS.items():
        if texto.lstrip().startswith(emoji):
            return clase
    return ""


# ---------------------------------------------------------------- parseo

def parsear_detalle(lineas):
    """Lista de lineas ya sin el '>' -> bloques y artefactos."""
    bloques = []
    artefactos = []
    parrafo = []
    vinetas = []

    def cerrar():
        if parrafo:
            bloques.append(("p", " ".join(parrafo)))
            parrafo.clear()
        if vinetas:
            bloques.append(("ul", list(vinetas)))
            vinetas.clear()

    for cruda in lineas:
        linea = cruda.rstrip()
        if not linea.strip():
            cerrar()
            continue
        despojada = linea.strip()

        if RE_ARTEFACTO.match(despojada):
            cerrar()
            artefactos.append(despojada)
            continue

        # Vineta: punto medio al principio.
        if despojada.startswith("·"):
            if parrafo:
                bloques.append(("p", " ".join(parrafo)))
                parrafo.clear()
            vinetas.append(despojada[1:].strip())
            continue

        # Continuacion indentada de la vineta anterior.
        if vinetas and linea.startswith("  "):
            vinetas[-1] += " " + despojada
            continue

        if vinetas:
            bloques.append(("ul", list(vinetas)))
            vinetas.clear()
        parrafo.append(despojada)

    cerrar()
    return bloques, artefactos


def parsear(ruta):
    texto = ruta.read_text(encoding="utf-8")
    seccion = None
    grupo = None
    tarea = None
    detalle = []
    contexto = []

    def cerrar_tarea():
        nonlocal tarea, detalle
        if tarea is not None:
            tarea["bloques"], tarea["artefactos"] = parsear_detalle(detalle)
            grupo["tareas"].append(tarea)
        tarea = None
        detalle = []

    for numero, linea in enumerate(texto.splitlines(), 1):
        m = RE_SECCION.match(linea)
        if m:
            if seccion is not None:
                raise ValueError(
                    "%s:%d dos cabeceras '## [slug]' en un mismo archivo"
                    % (ruta.name, numero)
                )
            seccion = {
                "slug": m.group(1).strip(),
                "titulo": m.group(2).strip(),
                "contexto": contexto,
                "grupos": [],
            }
            grupo = {"titulo": None, "tareas": []}
            seccion["grupos"].append(grupo)
            continue

        if seccion is None:
            continue

        m = RE_GRUPO.match(linea)
        if m:
            cerrar_tarea()
            grupo = {"titulo": m.group(1).strip(), "tareas": []}
            seccion["grupos"].append(grupo)
            continue

        m = RE_TAREA.match(linea)
        if m:
            cerrar_tarea()
            titulo = m.group(3).strip()
            fecha = None
            f = RE_FECHA.search(titulo)
            if f:
                fecha = f.group(1)
                titulo = titulo[: f.start()].strip()
            tarea = {
                "id": m.group(2),
                "titulo": titulo,
                "hecha": m.group(1).lower() == "x",
                "fecha": fecha,
            }
            continue

        m = RE_DETALLE.match(linea)
        if m and tarea is not None:
            detalle.append(m.group(1))
            continue

        if tarea is None and linea.strip():
            contexto.append(linea.strip())
        elif tarea is None and contexto and contexto[-1] != "":
            contexto.append("")

    cerrar_tarea()

    if seccion is None:
        raise ValueError("%s no tiene cabecera '## [slug] Titulo'" % ruta.name)

    # El contexto se agrupo como lineas sueltas; se rearma en parrafos.
    parrafos = []
    actual = []
    for linea in seccion["contexto"]:
        if linea:
            actual.append(linea)
        elif actual:
            parrafos.append(" ".join(actual))
            actual = []
    if actual:
        parrafos.append(" ".join(actual))
    seccion["contexto"] = parrafos

    seccion["grupos"] = [g for g in seccion["grupos"] if g["tareas"]]
    return seccion


# ---------------------------------------------------------------- render

def render_tarea(t):
    estado = "hecha" if t["hecha"] else "pendiente"
    o = []
    o.append('<li class="tarea %s" data-hecha="%d">' % (estado, int(t["hecha"])))
    o.append('  <div class="cabecera">')
    o.append('    <span class="casilla" aria-hidden="true"></span>')
    o.append('    <span class="ident">%s</span>' % html.escape(t["id"]))
    o.append('    <span class="titulo">%s</span>' % inline(t["titulo"]))
    if t["fecha"]:
        o.append('    <span class="fecha">%s</span>' % t["fecha"])
    o.append("  </div>")

    if t["bloques"] or t["artefactos"]:
        o.append('  <div class="detalle">')
        for tipo, contenido in t["bloques"]:
            if tipo == "p":
                c = clase_marca(contenido)
                o.append(
                    "    <p%s>%s</p>"
                    % (' class="%s"' % c if c else "", inline(contenido))
                )
            else:
                o.append("    <ul>")
                for punto in contenido:
                    c = clase_marca(punto)
                    o.append(
                        "      <li%s>%s</li>"
                        % (' class="%s"' % c if c else "", inline(punto))
                    )
                o.append("    </ul>")
        for a in t["artefactos"]:
            o.append('    <p class="artefacto">%s</p>' % inline(a))
        o.append("  </div>")

    o.append("</li>")
    return "\n".join(o)


def render_seccion(s, activa):
    hechas = sum(
        1 for g in s["grupos"] for t in g["tareas"] if t["hecha"]
    )
    total = sum(len(g["tareas"]) for g in s["grupos"])
    pct = round(100 * hechas / total) if total else 0

    o = []
    o.append(
        '<section class="panel%s" id="panel-%s" role="tabpanel">'
        % (" activo" if activa else "", s["slug"])
    )
    o.append('  <h2>%s</h2>' % inline(s["titulo"]))
    for p in s["contexto"]:
        c = clase_marca(p)
        o.append(
            '  <p class="contexto%s">%s</p>'
            % (" " + c if c else "", inline(p))
        )
    o.append('  <div class="barra"><div class="relleno" style="width:%d%%"></div></div>' % pct)
    o.append(
        '  <p class="cuenta">%d de %d completadas</p>' % (hechas, total)
    )

    for g in s["grupos"]:
        if g["titulo"]:
            o.append("  <h3>%s</h3>" % inline(g["titulo"]))
        o.append('  <ul class="tareas">')
        for t in g["tareas"]:
            o.append(render_tarea(t))
        o.append("  </ul>")
    o.append("</section>")
    return "\n".join(o), hechas, total


ESTILO = """
:root{
  --fondo:#fbfaf7; --papel:#fff; --tinta:#1c1a17; --suave:#6b6558;
  --linea:#e4dfd4; --acento:#8a5a2b; --hecho:#3f7d4e; --pend:#b8b0a0;
  --caja:#f6f3ec; --alerta:#c2410c; --aviso:#a16207;
}
@media (prefers-color-scheme:dark){
  :root{
    --fondo:#15140f; --papel:#1d1b16; --tinta:#eae5da; --suave:#a39b8b;
    --linea:#332f27; --acento:#d9a066; --hecho:#6bbf83; --pend:#5a5346;
    --caja:#232019; --alerta:#f97316; --aviso:#eab308;
  }
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--fondo); color:var(--tinta);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
}
.envoltura{max-width:900px; margin:0 auto; padding:2rem 1.25rem 5rem}
header.principal{border-bottom:2px solid var(--linea); padding-bottom:1.25rem; margin-bottom:1.5rem}
header.principal h1{margin:0 0 .3rem; font-size:1.6rem; letter-spacing:-.01em}
header.principal .sub{margin:0; color:var(--suave); font-size:.9rem}
header.principal .global{margin:.6rem 0 0; font-size:.9rem; color:var(--suave)}
header.principal .global strong{color:var(--tinta)}

nav.pestanas{display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:1.25rem}
nav.pestanas button{
  font:inherit; font-size:.88rem; cursor:pointer; padding:.45rem .85rem;
  border:1px solid var(--linea); background:var(--papel); color:var(--suave);
  border-radius:999px; transition:.15s;
}
nav.pestanas button:hover{border-color:var(--acento); color:var(--tinta)}
nav.pestanas button.activa{background:var(--acento); border-color:var(--acento); color:#fff}
nav.pestanas button .n{opacity:.7; font-variant-numeric:tabular-nums; margin-left:.35rem}

.controles{display:flex; align-items:center; gap:.5rem; margin-bottom:1.5rem; font-size:.88rem; color:var(--suave)}
.controles label{display:flex; align-items:center; gap:.4rem; cursor:pointer}

.panel{display:none}
.panel.activo{display:block}
.panel h2{font-size:1.25rem; margin:0 0 .6rem}
.panel h3{font-size:.8rem; text-transform:uppercase; letter-spacing:.08em;
  color:var(--suave); margin:2rem 0 .75rem; font-weight:600}
p.contexto{color:var(--suave); font-size:.93rem; margin:0 0 .7rem}
p.contexto.aviso{color:var(--aviso); border-left:3px solid var(--aviso);
  padding-left:.75rem; background:var(--caja)}

.barra{height:5px; background:var(--linea); border-radius:99px; overflow:hidden; margin:1rem 0 .4rem}
.barra .relleno{height:100%; background:var(--hecho); border-radius:99px}
p.cuenta{margin:0 0 .5rem; font-size:.82rem; color:var(--suave); font-variant-numeric:tabular-nums}

ul.tareas{list-style:none; padding:0; margin:0}
li.tarea{background:var(--papel); border:1px solid var(--linea);
  border-radius:10px; padding:.85rem 1rem; margin-bottom:.6rem}
li.tarea.hecha{opacity:.82}
.cabecera{display:flex; align-items:baseline; gap:.55rem; flex-wrap:wrap}
.casilla{width:14px; height:14px; border-radius:4px; flex:none;
  border:2px solid var(--pend); align-self:center}
li.tarea.hecha .casilla{background:var(--hecho); border-color:var(--hecho); position:relative}
li.tarea.hecha .casilla::after{content:"";position:absolute;left:3px;top:0px;
  width:4px;height:8px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(42deg)}
.ident{font:600 .74rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.04em; color:var(--acento); background:var(--caja);
  padding:.25rem .45rem; border-radius:5px; flex:none}
.titulo{font-weight:600; flex:1 1 12rem; min-width:0}
li.tarea.hecha .titulo{font-weight:500; text-decoration:line-through;
  text-decoration-color:var(--pend); text-decoration-thickness:1px}
.fecha{font-size:.74rem; color:var(--suave); font-variant-numeric:tabular-nums; flex:none}

.detalle{margin:.7rem 0 0; padding:.7rem .85rem; background:var(--caja);
  border-radius:8px; font-size:.9rem; color:var(--suave)}
.detalle p{margin:0 0 .55rem}
.detalle p:last-child{margin-bottom:0}
.detalle strong{color:var(--tinta)}
.detalle ul{margin:.2rem 0 .55rem; padding-left:1.1rem}
.detalle li{margin-bottom:.3rem}
.detalle p.alerta,.detalle li.alerta{color:var(--tinta);
  border-left:3px solid var(--alerta); padding-left:.6rem; margin-left:-.15rem}
.detalle p.aviso,.detalle li.aviso{border-left:3px solid var(--aviso); padding-left:.6rem}
.detalle p.artefacto{font-size:.82rem; padding-top:.45rem;
  border-top:1px dashed var(--linea); margin-top:.6rem; color:var(--suave)}
code{font:.86em ui-monospace,SFMono-Regular,Menlo,monospace;
  background:var(--fondo); padding:.1rem .3rem; border-radius:4px;
  border:1px solid var(--linea); word-break:break-word}
.detalle a{color:var(--acento)}
.mate{font-style:normal}

footer{margin-top:3rem; padding-top:1rem; border-top:1px solid var(--linea);
  font-size:.78rem; color:var(--suave)}
footer code{font-size:.9em}
@media (max-width:560px){
  .envoltura{padding:1.25rem .85rem 4rem}
  .fecha{width:100%}
}
"""

GUION = """
(function(){
  var CLAVE_PESTANA="propuesta_tesis_pestana", CLAVE_OCULTAR="propuesta_tesis_ocultar";
  var botones=document.querySelectorAll("nav.pestanas button");
  var paneles=document.querySelectorAll(".panel");
  function activar(slug){
    var hallado=false;
    paneles.forEach(function(p){
      var si=(p.id==="panel-"+slug);
      p.classList.toggle("activo",si); if(si) hallado=true;
    });
    if(!hallado) return false;
    botones.forEach(function(b){b.classList.toggle("activa",b.dataset.slug===slug);});
    try{localStorage.setItem(CLAVE_PESTANA,slug);}catch(e){}
    return true;
  }
  botones.forEach(function(b){
    b.addEventListener("click",function(){activar(b.dataset.slug);});
  });
  var guardada=null;
  try{guardada=localStorage.getItem(CLAVE_PESTANA);}catch(e){}
  if(!guardada||!activar(guardada)){activar(botones[0].dataset.slug);}

  var casilla=document.getElementById("ocultar");
  function aplicar(){
    document.querySelectorAll('li.tarea[data-hecha="1"]').forEach(function(t){
      t.style.display=casilla.checked?"none":"";
    });
    try{localStorage.setItem(CLAVE_OCULTAR,casilla.checked?"1":"0");}catch(e){}
  }
  try{casilla.checked=(localStorage.getItem(CLAVE_OCULTAR)==="1");}catch(e){}
  casilla.addEventListener("change",aplicar);
  aplicar();
})();
"""

MATHJAX = """
<script>
window.MathJax={
  tex:{inlineMath:[["$","$"]]},
  options:{skipHtmlTags:["script","noscript","style","textarea","pre","code"]}
};
</script>
<script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
"""


def construir():
    fuentes = [RAIZ / "TODO.md"]
    fuentes += sorted((RAIZ / "subproyectos").glob("*/TODO.md"))

    secciones = []
    for ruta in fuentes:
        if not ruta.exists():
            continue
        try:
            secciones.append(parsear(ruta))
        except ValueError as e:
            print("ERROR de formato: %s" % e, file=sys.stderr)
            return 1

    if not secciones:
        print("ERROR: no se encontro ningun TODO.md", file=sys.stderr)
        return 1

    def clave(s):
        slug = s["slug"]
        return (ORDEN.index(slug) if slug in ORDEN else len(ORDEN), slug)

    secciones.sort(key=clave)

    paneles, botones = [], []
    gh, gt = 0, 0
    for i, s in enumerate(secciones):
        cuerpo, hechas, total = render_seccion(s, i == 0)
        paneles.append(cuerpo)
        gh += hechas
        gt += total
        etiqueta = ETIQUETAS.get(s["slug"], s["slug"].replace("_", " "))
        aviso = ""
        if any("⚠️" in p for p in s["contexto"]):
            aviso = "⚠️ "
        botones.append(
            '<button data-slug="%s" role="tab">%s%s<span class="n">%d/%d</span></button>'
            % (s["slug"], aviso, html.escape(etiqueta), hechas, total)
        )

    hoy = date.today().isoformat()
    o = []
    o.append("<!doctype html>")
    o.append('<html lang="es">')
    o.append("<head>")
    o.append('<meta charset="utf-8">')
    o.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    o.append("<title>Propuesta de tesis · TODO</title>")
    o.append(
        "<!-- GENERADO por web/build_todo.py el %s. NO EDITAR A MANO: "
        "los TODO.md mandan, este archivo se reescribe. -->" % hoy
    )
    o.append("<style>%s</style>" % ESTILO)
    o.append(MATHJAX)
    o.append("</head>")
    o.append("<body>")
    o.append('<div class="envoltura">')
    o.append('<header class="principal">')
    o.append("<h1>Propuesta de tesis — control óptimo</h1>")
    o.append(
        '<p class="sub">Decidir y proponer un tema en control óptimo inverso, '
        "en 2–3 meses desde el 2026-07-25.</p>"
    )
    o.append(
        '<p class="global"><strong>%d</strong> de <strong>%d</strong> tareas '
        "completadas en todo el proyecto.</p>" % (gh, gt)
    )
    o.append("</header>")
    o.append('<nav class="pestanas" role="tablist">')
    o.extend(botones)
    o.append("</nav>")
    o.append('<div class="controles">')
    o.append(
        '<label><input type="checkbox" id="ocultar"> Esconder las completadas</label>'
    )
    o.append("</div>")
    o.extend(paneles)
    o.append("<footer>")
    o.append(
        "Generado el %s por <code>web/build_todo.py</code> a partir de los "
        "<code>TODO.md</code>. Editar esta página a mano no sirve de nada: "
        "se reescribe en la siguiente ejecución." % hoy
    )
    o.append("</footer>")
    o.append("</div>")
    o.append("<script>%s</script>" % GUION)
    o.append("</body>")
    o.append("</html>")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text("\n".join(o), encoding="utf-8")

    print("OK  %s" % SALIDA.relative_to(RAIZ))
    for s in secciones:
        h = sum(1 for g in s["grupos"] for t in g["tareas"] if t["hecha"])
        n = sum(len(g["tareas"]) for g in s["grupos"])
        print("    %-20s %2d/%2d" % (s["slug"], h, n))
    print("    %-20s %2d/%2d" % ("TOTAL", gh, gt))
    return 0


if __name__ == "__main__":
    sys.exit(construir())
