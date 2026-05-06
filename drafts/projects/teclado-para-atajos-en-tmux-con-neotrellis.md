Title: Teclado para atajos en tmux con Neotrellis
Date: 2026-03-17
Category: projects
Slug: teclado-para-atajos-en-tmux-con-neotrellis

---
Este es un teclado 4x4 para atajos que usamos con tmux. Lo armamos para no depender tanto del teclado principal y tener las acciones mas usadas siempre a mano. El firmware esta en [https://github.com/psyrax/tmuxboard](https://github.com/psyrax/tmuxboard).

![Teclado para tmux]({static}/images/tmuxboard.jpg)

## Hardware

- RP2040 Pro Micro
- Adafruit NeoTrellis 4x4

## Capas y uso

El teclado tiene dos capas. La tecla 15 (esquina inferior derecha) cambia de capa.

- Capa 0: atajos generales del sistema y navegador (editar, ventanas, media).
- Capa 1: atajos de tmux. Todas las teclas envian el prefijo Ctrl+B automaticamente.

## Mapa base (Capa 0)

En la capa base tenemos acciones comunes como deshacer, guardar, copiar, pegar, abrir terminal, cambiar pestañas y controles de media. Es una capa pensada para el dia a dia fuera de tmux.

## Mapa tmux (Capa 1)

La capa de tmux esta orientada a navegacion y manejo de ventanas/paneles:

- mover entre paneles con flechas
- splits vertical y horizontal
- nueva ventana, siguiente/anterior
- zoom del panel, modo scroll/copia
- matar panel o ventana y desconectar sesion

## Colores de LEDs

Los LEDs indican en que contexto estas:

- Azul: edicion (Capa 0)
- Cian: sistema / navegador (Capa 0)
- Morado: ventanas (Capa 0)
- Naranja: media (Capa 0)
- Verde: tmux navegacion/ventanas (Capa 1)
- Rojo: tmux matar/desconectar (Capa 1)
- Amarillo: tecla de cambio de capa
- Blanco: flash de confirmacion

Si quieres el mapa completo de teclas y los layouts exactos por capa, esta en el README del repositorio.