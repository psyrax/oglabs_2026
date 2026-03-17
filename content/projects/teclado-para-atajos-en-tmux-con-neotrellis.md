Title: Teclado para Atajos en tmux con Neotrellis
Date: 2026-03-17
Category: projects
Slug: teclado-para-atajos-en-tmux-con-neotrellis

---

Este teclado 4x4 está diseñado para facilitar el uso de atajos en tmux, permitiéndonos no depender tanto del teclado principal y tener las acciones más utilizadas siempre al alcance. El firmware está disponible en [GitHub](https://github.com/psyrax/tmuxboard).

![Teclado para tmux]({static}/images/tmuxboard.jpg)

## Hardware

- RP2040 Pro Micro
- Adafruit NeoTrellis 4x4

## Capas y Uso

El teclado cuenta con dos capas. La tecla 15 (esquina inferior derecha) se utiliza para cambiar de capa.

- **Capa 0**: Atajos generales del sistema y navegador (editar, ventanas, media).
- **Capa 1**: Atajos de tmux. Todas las teclas envían automáticamente el prefijo Ctrl+B.

## Mapa Base (Capa 0)

En la capa base disponemos de acciones comunes como deshacer, guardar, copiar, pegar, abrir terminal, cambiar pestañas y controles de media. Es una capa diseñada para el uso diario fuera de tmux.

## Mapa tmux (Capa 1)

La capa de tmux está orientada a la navegación y la gestión de ventanas/paneles:

- Mover entre paneles con flechas
- Splits vertical y horizontal
- Nueva ventana, siguiente/anterior
- Zoom del panel, modo scroll/copia
- Eliminar panel o ventana y desconectar sesión

## Colores de LEDs

Los LEDs indican el contexto en el que te encuentras:

- Azul: Edición (Capa 0)
- Cian: Sistema / Navegador (Capa 0)
- Morado: Ventanas (Capa 0)
- Naranja: Media (Capa 0)
- Verde: Navegación/Ventanas de tmux (Capa 1)
- Rojo: Eliminar/Desconectar en tmux (Capa 1)
- Amarillo: Tecla de cambio de capa
- Blanco: Flash de confirmación

Si deseas consultar el mapa completo de teclas y los layouts exactos por capa, puedes encontrarlos en el README del repositorio.
