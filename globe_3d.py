import ctypes
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

# Config
NUM_NODOS = 1800
NUM_CONNECTIONS = 3000
WIDTH, HEIGHT = 1280, 720
DARK_BG = (0.008, 0.008, 0.03)
SHADERS_DIR = Path(__file__).parent / "shaders"


def _carregar_shader(caminho: Path, tipo: int) -> int:
    with open(caminho, "r") as f:
        src = f.read()
    shader = glCreateShader(tipo)
    glShaderSource(shader, src)
    glCompileShader(shader)
    if not glGetShaderiv(shader, GL_COMPILE_STATUS):
        err = glGetShaderInfoLog(shader)
        raise RuntimeError(f"Erro ao compilar {caminho.name}:\n{err.decode()}")
    return shader


def criar_programa() -> int:
    vs = _carregar_shader(SHADERS_DIR / "pulse.vert", GL_VERTEX_SHADER)
    fs = _carregar_shader(SHADERS_DIR / "pulse.frag", GL_FRAGMENT_SHADER)
    prog = glCreateProgram()
    glAttachShader(prog, vs)
    glAttachShader(prog, fs)
    glLinkProgram(prog)
    if not glGetProgramiv(prog, GL_LINK_STATUS):
        err = glGetProgramInfoLog(prog)
        raise RuntimeError(f"Erro ao linkar programa:\n{err.decode()}")
    glDeleteShader(vs)
    glDeleteShader(fs)
    return prog


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------

def gerar_face() -> np.ndarray:
    verts = np.zeros((NUM_NODOS, 3), dtype=np.float32)
    for i in range(NUM_NODOS):
        theta = random.random() * 2 * math.pi
        phi = math.acos(2 * random.random() - 1)
        r = 1.2 + (random.random() - 0.5) * 0.06
        x = r * math.sin(phi) * math.cos(theta)
        y = -r * math.cos(phi) * 1.35
        z = r * math.sin(phi) * math.sin(theta)
        bot = max(0, (phi - math.pi * 0.45) / (math.pi * 0.5))
        if bot > 0:
            s = 1 - bot * 0.35
            x *= s
            z *= s
        if z > 0:
            z *= 0.88
        else:
            z *= 0.85
        verts[i] = [x, y, z]
    return verts


def gerar_cores(verts: np.ndarray) -> np.ndarray:
    cores = np.zeros((NUM_NODOS, 3), dtype=np.float32)
    for i in range(NUM_NODOS):
        px, py, pz = verts[i]
        frontness = max(0, min(1, (pz + 0.5) / 1.5))
        is_front = frontness > 0.1 and abs(py) < 1.3
        if not is_front:
            cores[i] = [0.02, 0.03, 0.06]
            continue

        nx, ny = px / 1.3, py / 1.5
        land = (math.sin(nx * 4 + ny * 3) * math.cos(ny * 5 + nx * 2)
                + math.sin(nx * 7 + ny * 5) * 0.4
                + math.cos(nx * 2 - ny * 6) * 0.3)
        is_land = land > 0.05

        eR = math.sqrt((px - 0.45)**2 + (py - 0.25)**2)
        eL = math.sqrt((px + 0.45)**2 + (py - 0.25)**2)
        nD = math.sqrt(px * px + (py + 0.3)**2)
        is_special = eR < 0.2 or eL < 0.2 or nD < 0.18

        if is_special:
            bt = 0.7 + random.random() * 0.3
            cores[i] = [bt, 0.02, bt * 0.5]
        else:
            sh = 0.5 + random.random() * 0.4
            if is_land:
                g = (0.2 + random.random() * 0.3) * sh
                cores[i] = [(0.06 + random.random() * 0.06) * sh,
                            g,
                            (0.03 + random.random() * 0.03) * sh]
            else:
                cores[i] = [(0.02 + random.random() * 0.03) * sh,
                            (0.05 + random.random() * 0.08) * sh,
                            (0.2 + random.random() * 0.2) * sh]

            ov = 0.1 * math.sin(px * 10 + py * 8 + pz * 6) * frontness
            cores[i][0] = min(1, cores[i][0] + ov * 0.15)
            cores[i][1] = min(1, cores[i][1] + ov * 0.8)
            cores[i][2] = min(1, cores[i][2] + ov * 0.4)
    return cores


def gerar_conexoes(verts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lines = []
    colors = []
    for _ in range(NUM_CONNECTIONS):
        a = random.randrange(NUM_NODOS)
        b = random.randrange(NUM_NODOS)
        if a == b:
            continue
        dx = verts[a] - verts[b]
        dist = math.sqrt(dx @ dx)
        if dist > 0.8 or dist < 0.1:
            continue
        lines.extend([verts[a][0], verts[a][1], verts[a][2],
                      verts[b][0], verts[b][1], verts[b][2]])
        bri = max(0.1, 1 - dist / 0.8) * 0.5
        near_face = verts[a, 2] > 0.3 or verts[b, 2] > 0.3
        is_magenta = random.random() < 0.15 or (near_face and random.random() < 0.3)
        if is_magenta:
            colors.extend([bri, 0, bri * 0.4, bri, 0, bri * 0.4])
        else:
            colors.extend([0, bri * 0.9, bri * 0.7, 0, bri * 0.9, bri * 0.7])
    return (np.array(lines, dtype=np.float32),
            np.array(colors, dtype=np.float32))


# ---------------------------------------------------------------------------
# OpenGL / Shaders
# ---------------------------------------------------------------------------

def init_gl() -> int:
    glClearColor(*DARK_BG, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glPointSize(2.5)
    glEnable(GL_PROGRAM_POINT_SIZE)

    prog = criar_programa()
    glUseProgram(prog)
    return prog


def criar_vao(verts: np.ndarray, colors: np.ndarray) -> int:
    vao = glGenVertexArrays(1)
    glBindVertexArray(vao)

    vbo_pos = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_pos)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
    glEnableVertexAttribArray(0)

    vbo_col = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_col)
    glBufferData(GL_ARRAY_BUFFER, colors.nbytes, colors, GL_STATIC_DRAW)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
    glEnableVertexAttribArray(1)

    glBindVertexArray(0)
    return vao


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(prog: int, vao_nodes: int, n_nodes: int,
           vao_lines: int, n_lines: int,
           rot_y: float, amp: float, elapsed: float):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # --- Matriz MVP ---
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(40, WIDTH / HEIGHT, 0.1, 50.0)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(0.0, 0.2, -4.5)
    glRotatef(rot_y, 0, 1, 0)
    s = 1 + amp * 0.02
    glScalef(s, s, s)

    proj = (ctypes.c_float * 16)()
    mv = (ctypes.c_float * 16)()
    glGetFloatv(GL_PROJECTION_MATRIX, proj)
    glGetFloatv(GL_MODELVIEW_MATRIX, mv)
    proj_np = np.array(proj, dtype=np.float32).reshape(4, 4)
    mv_np = np.array(mv, dtype=np.float32).reshape(4, 4)
    mvp = (proj_np @ mv_np).T  # OpenGL column-major

    mvp_loc = glGetUniformLocation(prog, "u_mvp")
    time_loc = glGetUniformLocation(prog, "u_time")
    is_line_loc = glGetUniformLocation(prog, "u_is_line")

    glUniformMatrix4fv(mvp_loc, 1, GL_TRUE, mvp)

    # --- Draw nodes (u_is_line = 0) ---
    glUniform1i(is_line_loc, 0)
    glUniform1f(time_loc, elapsed)
    glPointSize(2.0 + amp * 3.0)
    glBindVertexArray(vao_nodes)
    glDrawArrays(GL_POINTS, 0, n_nodes)

    # --- Draw connections (u_is_line = 1) ---
    if n_lines > 0:
        glUniform1i(is_line_loc, 1)
        glUniform1f(time_loc, elapsed)
        glLineWidth(1.0)
        glBindVertexArray(vao_lines)
        glDrawArrays(GL_LINES, 0, n_lines)

    glBindVertexArray(0)

    # --- Rings (fixed-function, simples) ---
    glUseProgram(0)
    glDisable(GL_DEPTH_TEST)
    glLineWidth(1)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(40, WIDTH / HEIGHT, 0.1, 50.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glTranslatef(0.0, 0.2, -4.5)
    glRotatef(rot_y, 0, 1, 0)

    glBegin(GL_LINE_LOOP)
    glColor4f(0, 0.8, 0.6, 0.06 + amp * 0.08)
    for i in range(81):
        a = (i / 80) * 2 * math.pi
        glVertex3f(math.cos(a) * 2.0, math.sin(a) * 2.0 * 0.25, 0)
    glEnd()
    glBegin(GL_LINE_LOOP)
    glColor4f(1.0, 0, 0.4, 0.03 + amp * 0.04)
    for i in range(81):
        a = (i / 80) * 2 * math.pi
        glVertex3f(math.cos(a + 1.0) * 2.6, math.sin(a + 1.0) * 2.6 * 0.25, 0.3)
    glEnd()
    glEnable(GL_DEPTH_TEST)

    glUseProgram(prog)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    display = (WIDTH, HEIGHT)
    pygame.display.set_mode(display, pygame.DOUBLEBUF | pygame.OPENGL)
    pygame.display.set_caption("Viviane - Neural Core 3D")
    prog = init_gl()

    verts = gerar_face()
    cores = gerar_cores(verts)
    line_verts, line_colors = gerar_conexoes(verts)

    vao_nodes = criar_vao(verts, cores)
    vao_lines = criar_vao(line_verts, line_colors)
    n_l = len(line_verts) // 3 if len(line_verts) > 0 else 0

    clock = pygame.time.Clock()
    rot_y = 0.0
    start = time.time()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        dt = clock.tick(60) / 1000.0
        elapsed = time.time() - start

        rot_y += 15 * dt
        if rot_y > 360:
            rot_y -= 360

        amp = max(0, math.sin(elapsed * 0.5) * 0.3 + 0.1)

        render(prog, vao_nodes, NUM_NODOS, vao_lines, n_l,
               rot_y, amp, elapsed)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
