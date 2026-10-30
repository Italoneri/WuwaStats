"""Atalhos globais para tirar prints do Wuthering Waves e analisar sem sair do jogo (só Windows).

    uv run python scripts/captura.py Suoming                 # build deduzida se o personagem tiver só uma
    uv run python scripts/captura.py Suoming --build Suoming_DPS

F8   print do echo aberto      -> input/<personagem>/echo_N.png (N em sequência, até 5)
F9   tela do personagem (arma) -> input/<personagem>/personagem.png (substitui o anterior)
F10  extrai a pasta com a IA de visão e abre a análise no navegador

Só lê a tela: escuta os atalhos com RegisterHotKey, localiza a janela pelo título e captura a área dela com mss.
Nunca envia cliques nem teclas ao jogo. Ctrl+C encerra.
"""

import argparse
import ctypes
import io
import re
import subprocess
import sys
import threading
import time
import webbrowser
import winsound
from collections.abc import Callable, Mapping
from ctypes import wintypes
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import mss
import mss.exception
import mss.tools

from wuwastats.config import PROJECT_ROOT, Settings
from wuwastats.domain.models import MAX_ECHOS
from wuwastats.domain.names import fold
from wuwastats.domain.tables import Perfil
from wuwastats.gamedata.loader import GameDataError, load_game_data

TITULO_PADRAO = "Wuthering Waves"
PORTA_PADRAO = 8000
PASTA_INPUT = PROJECT_ROOT / "input"
ARQUIVO_PERSONAGEM = "personagem.png"
ARQUIVO_ENTRADA = "entrada.json"
TIMEOUT_EXTRACAO_S = 300
TIMEOUT_SERVIDOR_S = 20
NOME_VALIDO = re.compile(r"^[\w\- ]+$")
PRINT_ECHO = re.compile(r"^echo_(\d+)\.png$", re.IGNORECASE)

VK_F8, VK_F9, VK_F10 = 0x77, 0x78, 0x79
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
ERROR_ACCESS_DENIED = 5
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class CapturaFalhou(Exception):
    pass


class BuildIndefinida(Exception):
    pass


# --- Regras puras ---


def proximo_print_echo(pasta: Path) -> Path:
    """echo_1..echo_5: a extração lê em ordem alfabética e o 1º é o echo principal."""
    numeros = [int(m.group(1)) for arquivo in pasta.glob("*.png") if (m := PRINT_ECHO.match(arquivo.name))]
    if len(numeros) >= MAX_ECHOS:
        raise CapturaFalhou(f"já há {MAX_ECHOS} prints de echo em {pasta}; apague um para tirar outro")
    return pasta / f"echo_{max(numeros, default=0) + 1}.png"


def escolher_build(perfis: Mapping[str, Perfil], personagem: str, build: str | None) -> str:
    if build is not None:
        if build not in perfis:
            raise BuildIndefinida(f"build '{build}' não existe em characters.json. Disponíveis: {', '.join(sorted(perfis))}")
        return build
    do_personagem = sorted(chave for chave, perfil in perfis.items() if fold(perfil.personagem) == fold(personagem))
    if len(do_personagem) == 1:
        return do_personagem[0]
    if not do_personagem:
        raise BuildIndefinida(f"nenhuma build de '{personagem}' em characters.json")
    raise BuildIndefinida(f"'{personagem}' tem várias builds ({', '.join(do_personagem)}); escolha com --build")


def url_resultado(porta: int, entrada_json: str) -> str:
    """A página lê a entrada do hash: não vai para o servidor nem para o histórico de requisições."""
    return f"http://127.0.0.1:{porta}/#entrada={quote(entrada_json, safe='')}"


# --- Sessão e atalhos ---


@dataclass
class Sessao:
    pasta: Path
    titulo: str
    porta: int
    build: str | None
    servidor: subprocess.Popen[bytes] | None = None
    analisando: threading.Lock = field(default_factory=threading.Lock)

    def capturar_echo(self) -> None:
        self._capturar(proximo_print_echo(self.pasta))

    def capturar_personagem(self) -> None:
        self._capturar(self.pasta / ARQUIVO_PERSONAGEM)

    def _capturar(self, destino: Path) -> None:
        regiao = regiao_da_janela(self.titulo)
        with mss.MSS() as tela:
            imagem = tela.grab(regiao)
        mss.tools.to_png(imagem.rgb, imagem.size, output=str(destino))
        print(f"  salvo {destino.relative_to(PROJECT_ROOT)} ({imagem.width}x{imagem.height})")
        som_ok()

    def analisar(self) -> None:
        """Roda numa thread para F8/F9 continuarem respondendo durante a chamada à IA."""
        if self.build is None:
            raise CapturaFalhou("sem build definida; reinicie com --build")
        if not self.analisando.acquire(blocking=False):
            raise CapturaFalhou("uma análise já está em andamento")
        threading.Thread(target=self._analisar_em_segundo_plano, args=(self.build,), name="analise", daemon=True).start()

    def _analisar_em_segundo_plano(self, build: str) -> None:
        try:
            som_inicio()
            entrada = extrair_pasta(self.pasta, build)
            self._garantir_servidor()
            webbrowser.open(url_resultado(self.porta, entrada))
            print("  análise aberta no navegador")
            som_ok()
        except (CapturaFalhou, OSError, subprocess.SubprocessError) as erro:
            print(f"  ERRO: {erro}", file=sys.stderr)
            som_erro()
        finally:
            self.analisando.release()

    def _garantir_servidor(self) -> None:
        if api_no_ar(self.porta):
            return
        print(f"  subindo a API em http://127.0.0.1:{self.porta}")
        comando = [sys.executable, "-m", "wuwastats.cli", "serve", "--port", str(self.porta)]
        self.servidor = subprocess.Popen(comando, cwd=PROJECT_ROOT)
        limite = time.monotonic() + TIMEOUT_SERVIDOR_S
        while time.monotonic() < limite:
            if self.servidor.poll() is not None:
                raise CapturaFalhou(f"a API encerrou ao subir (código {self.servidor.returncode})")
            if api_no_ar(self.porta):
                return
            time.sleep(0.3)
        raise CapturaFalhou(f"a API não respondeu em {TIMEOUT_SERVIDOR_S}s")

    def encerrar(self) -> None:
        if self.servidor is not None and self.servidor.poll() is None:
            self.servidor.terminate()
            self.servidor.wait(timeout=10)


def extrair_pasta(pasta: Path, build: str) -> str:
    saida = pasta / ARQUIVO_ENTRADA
    comando = [sys.executable, "-m", "wuwastats.cli", "extract", str(pasta), "--build", build, "--saida", str(saida)]
    print(f"  extraindo {pasta.relative_to(PROJECT_ROOT)} com a build {build}...")
    resultado = subprocess.run(comando, cwd=PROJECT_ROOT, timeout=TIMEOUT_EXTRACAO_S, check=False)
    if resultado.returncode != 0:
        raise CapturaFalhou(f"extração falhou (código {resultado.returncode}); veja as mensagens acima")
    return saida.read_text(encoding="utf-8")


def api_no_ar(porta: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{porta}/api/health", timeout=1) as resposta:
            return resposta.status == 200
    except (URLError, TimeoutError, ConnectionError):
        return False


def escutar_atalhos(acoes: Mapping[int, Callable[[], None]]) -> None:
    """Fila de mensagens da thread; PeekMessage + sleep deixa o Ctrl+C funcionar."""
    user32 = _user32()
    por_id = dict(enumerate(acoes.items(), start=1))
    registrados: list[int] = []
    try:
        for identificador, (tecla, _acao) in por_id.items():
            if not user32.RegisterHotKey(None, identificador, MOD_NOREPEAT, tecla):
                raise CapturaFalhou(f"não consegui registrar a tecla 0x{tecla:X}: outro programa já usa esse atalho")
            registrados.append(identificador)
        mensagem = wintypes.MSG()
        while True:
            if user32.PeekMessageW(ctypes.byref(mensagem), None, 0, 0, PM_REMOVE):
                if mensagem.message == WM_HOTKEY:
                    _executar(por_id[mensagem.wParam][1])
            else:
                time.sleep(0.05)
    finally:
        for identificador in registrados:
            user32.UnregisterHotKey(None, identificador)


def _executar(acao: Callable[[], None]) -> None:
    try:
        acao()
    except (CapturaFalhou, OSError, mss.exception.ScreenShotError) as erro:
        print(f"  ERRO: {erro}", file=sys.stderr)
        som_erro()


# --- Janela (só leitura) ---


def regiao_da_janela(titulo: str) -> dict[str, int]:
    """Área interna (sem borda/barra de título) em pixels físicos da tela."""
    user32 = _user32()
    hwnd = _localizar_janela(titulo)
    if user32.IsIconic(hwnd):
        raise CapturaFalhou("a janela do jogo está minimizada")
    if user32.GetForegroundWindow() != hwnd:
        raise CapturaFalhou("o jogo não está em primeiro plano; outra janela sairia no print")
    retangulo = wintypes.RECT()
    origem = wintypes.POINT(0, 0)
    if not (user32.GetClientRect(hwnd, ctypes.byref(retangulo)) and user32.ClientToScreen(hwnd, ctypes.byref(origem))):
        raise CapturaFalhou(f"não consegui ler a posição da janela (erro {ctypes.get_last_error()})")
    if retangulo.right <= 0 or retangulo.bottom <= 0:
        raise CapturaFalhou("a janela do jogo está sem área visível")
    return {"left": origem.x, "top": origem.y, "width": retangulo.right, "height": retangulo.bottom}


def _localizar_janela(titulo: str) -> int:
    janelas = _janelas_visiveis()
    encontradas = [hwnd for hwnd, texto in janelas.items() if texto.strip().casefold() == titulo.casefold()]
    if encontradas:
        return encontradas[0]
    parecidas = sorted({texto for texto in janelas.values() if "wuthering" in texto.casefold()})
    dica = f" Janelas parecidas: {parecidas}; use --titulo." if parecidas else ""
    raise CapturaFalhou(f"janela '{titulo}' não encontrada.{dica}")


def _janelas_visiveis() -> dict[int, str]:
    user32 = _user32()
    janelas: dict[int, str] = {}

    @ENUM_WINDOWS_PROC
    def coletar(hwnd: int, _parametro: int) -> bool:
        tamanho = user32.GetWindowTextLengthW(hwnd)
        if tamanho and user32.IsWindowVisible(hwnd):
            texto = ctypes.create_unicode_buffer(tamanho + 1)
            user32.GetWindowTextW(hwnd, texto, tamanho + 1)
            janelas[hwnd] = texto.value
        return True

    user32.EnumWindows(coletar, 0)
    return janelas


@cache
def _user32() -> ctypes.WinDLL:
    """Assinaturas explícitas: sem elas o ctypes converte HWND (64 bits) para int de 32 bits."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = wintypes.HWND
    assinaturas: dict[str, tuple[list[type], type]] = {
        "EnumWindows": ([ENUM_WINDOWS_PROC, wintypes.LPARAM], wintypes.BOOL),
        "GetWindowTextLengthW": ([hwnd], ctypes.c_int),
        "GetWindowTextW": ([hwnd, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        "IsWindowVisible": ([hwnd], wintypes.BOOL),
        "IsIconic": ([hwnd], wintypes.BOOL),
        "GetForegroundWindow": ([], hwnd),
        "GetClientRect": ([hwnd, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "ClientToScreen": ([hwnd, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
        "RegisterHotKey": ([hwnd, ctypes.c_int, wintypes.UINT, wintypes.UINT], wintypes.BOOL),
        "UnregisterHotKey": ([hwnd, ctypes.c_int], wintypes.BOOL),
        "PeekMessageW": ([ctypes.POINTER(wintypes.MSG), hwnd, wintypes.UINT, wintypes.UINT, wintypes.UINT], wintypes.BOOL),
        "SetProcessDpiAwarenessContext": ([ctypes.c_void_p], wintypes.BOOL),
    }
    for nome, (argumentos, retorno) in assinaturas.items():
        funcao = getattr(user32, nome)
        funcao.argtypes = argumentos
        funcao.restype = retorno
    return user32


def _ativar_dpi_real() -> None:
    """Sem isso, com escala do Windows acima de 100%, a posição da janela não bate com os pixels do mss."""
    user32 = _user32()
    if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
        return
    erro = ctypes.get_last_error()
    if erro != ERROR_ACCESS_DENIED:  # ACCESS_DENIED = já definido para o processo
        print(f"Aviso: não consegui ativar DPI por monitor (erro {erro}); prints podem sair cortados.", file=sys.stderr)


# --- Sons ---


def som_ok() -> None:
    winsound.Beep(1200, 80)


def som_inicio() -> None:
    winsound.Beep(800, 80)


def som_erro() -> None:
    winsound.Beep(300, 120)
    winsound.Beep(300, 120)


# --- Início ---


def main(argv: list[str] | None = None) -> int:
    for saida in (sys.stdout, sys.stderr):
        if isinstance(saida, io.TextIOWrapper):
            saida.reconfigure(encoding="utf-8")
    args = _argumentos(argv)
    if not NOME_VALIDO.match(args.personagem):
        print(f"Nome de personagem inválido para pasta: '{args.personagem}'", file=sys.stderr)
        return 1
    try:
        build = _build_da_sessao(args)
    except (GameDataError, BuildIndefinida) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    pasta = PASTA_INPUT / args.personagem
    pasta.mkdir(parents=True, exist_ok=True)
    sessao = Sessao(pasta=pasta, titulo=args.titulo, porta=args.porta, build=build)
    _ativar_dpi_real()
    print(f"Capturando '{args.titulo}' em {pasta.relative_to(PROJECT_ROOT)} · build {build or '(nenhuma: F10 desativado)'}")
    print("F8 echo · F9 tela do personagem · F10 analisar · Ctrl+C sai")
    try:
        escutar_atalhos({VK_F8: sessao.capturar_echo, VK_F9: sessao.capturar_personagem, VK_F10: sessao.analisar})
    except CapturaFalhou as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Encerrado.")
    finally:
        sessao.encerrar()
    return 0


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("personagem", help="nome do personagem; vira a pasta input/<personagem>/")
    parser.add_argument("--build", help="chave em characters.json (padrão: a única build do personagem)")
    parser.add_argument("--titulo", default=TITULO_PADRAO, help=f"título exato da janela do jogo (padrão: {TITULO_PADRAO})")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO, help="porta da API usada pelo F10")
    return parser.parse_args(argv)


def _build_da_sessao(args: argparse.Namespace) -> str | None:
    """--build errado aborta; sem --build e sem build única, só o F10 fica desativado."""
    perfis = load_game_data(Settings().data_dir).perfis
    try:
        return escolher_build(perfis, args.personagem, args.build)
    except BuildIndefinida as erro:
        if args.build is not None:
            raise
        print(f"Aviso: {erro}. Os prints funcionam; o F10 fica desativado.", file=sys.stderr)
        return None


if __name__ == "__main__":
    sys.exit(main())
