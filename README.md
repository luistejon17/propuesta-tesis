# Propuesta de tesis — páginas públicas

Dos páginas estáticas del proyecto **Propuesta_Tesis**, sobre control óptimo
inverso en tiempo continuo.

| Ruta | Qué es | Quién la mantiene |
|---|---|---|
| `/` | Estado de las tareas del proyecto | Generada. La escribe `build_todo.py` |
| `/tracker/` | Tracker de estudio | El usuario. Su estado viaja en el `?s=` de la URL |

Son dos y no una a propósito. El tracker guarda su progreso **en el enlace**, así
que es del usuario y se sincroniza entre sus PCs. La página de tareas lo guarda
**en el propio HTML**, así que tiene un enlace fijo que el asesor puede refrescar.
Fundirlas dejaría el tracker en 0 % para cualquiera que abriera el enlace sin
parámetros.

## Este repo es un destino de publicación, no la fuente

El contenido vive en el repositorio privado del proyecto, bajo `web/`, y llega
aquí con `git subtree push`. **El repositorio del proyecto no es público** y no
puede serlo: contiene transcripciones de reuniones privadas, fichas de trabajo no
publicado del asesor y material con derechos de autor.

## `index.html` no se edita a mano

Lo genera `build_todo.py` a partir de los `TODO.md` del proyecto, y cualquier
cambio manual se pierde en la siguiente ejecución. Las tareas se editan en los
`.md`; el HTML solo las muestra.

```
python web/build_todo.py
```

El script valida el formato y falla en la terminal, no en la página. Al terminar
imprime el recuento por subproyecto.

`/tracker/` es la excepción: hoy es un marcador de posición escrito a mano, y lo
sustituirá el artefacto de la tarea `REF-8`.
