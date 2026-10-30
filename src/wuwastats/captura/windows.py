"""Tela, atalhos globais e bipe no Windows. Só importar com sys.platform == "win32".

Só lê a tela: escuta F8/F9/F10 com RegisterHotKey, localiza a janela pelo título e captura a área dela com mss.
Nunca envia cliques nem teclas ao jogo (test_windows.py falha se alguém usar uma API que faça isso).
"""

import ctypes
import logging
import threading
import time
import winsound
from collections.abc import Callable, Mapping
from ctypes import wintypes
from functools import cache

import mss
import mss.exception
import mss.tools

from wuwastats.captura.servico import CapturaFalhou, FerramentasCaptura, Sinal, Tecla

TECLAS: dict[Tecla, int] = {"F8": 0x77, "F9": 0x78, "F10": 0x79}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
ERROR_ACCESS_DENIED = 5
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
TIMEOUT_REGISTRO_S = 5

logger = logging.getLogger(__name__)


def ferramentas_windows(titulo_janela: str) -> FerramentasCaptura:
    _ativar_dpi_real()
    return FerramentasCaptura(
        capturar_tela=lambda: capturar_janela(titulo_janela),
        escutar_atalhos=EscutaAtalhos.iniciar,
        sinalizar=sinalizar,
    )


def capturar_janela(titulo: str) -> bytes:
    regiao = regiao_da_janela(titulo)
    try:
        with mss.MSS() as tela:
            imagem = tela.grab(regiao)
    except mss.exception.ScreenShotError as erro:
        raise CapturaFalhou(f"print da tela falhou: {erro}") from erro
    png = mss.tools.to_png(imagem.rgb, imagem.size)
    if png is None:
        raise CapturaFalhou("o mss não devolveu a imagem")
    return png


def sinalizar(sinal: Sinal) -> None:
    """Retorno no jogo, sem olhar para a página: agudo = salvo, dois graves = erro."""
    if sinal == "ok":
        winsound.Beep(1200, 80)
        return
    winsound.Beep(300, 120)
    winsound.Beep(300, 120)


class EscutaAtalhos:
    """RegisterHotKey vale para a thread que registrou: a fila de mensagens é lida nessa mesma thread."""

    def __init__(self, acoes: Mapping[Tecla, Callable[[], None]]) -> None:
        self._acoes = dict(acoes)
        self._parar = threading.Event()
        self._registrado = threading.Event()
        self._erro: CapturaFalhou | None = None
        self._thread = threading.Thread(target=self._escutar, name="atalhos", daemon=True)

    @classmethod
    def iniciar(cls, acoes: Mapping[Tecla, Callable[[], None]]) -> "EscutaAtalhos":
        escuta = cls(acoes)
        escuta._thread.start()
        if not escuta._registrado.wait(TIMEOUT_REGISTRO_S):
            escuta.parar()
            raise CapturaFalhou(f"os atalhos não foram registrados em {TIMEOUT_REGISTRO_S}s")
        if escuta._erro is not None:
            raise escuta._erro
        return escuta

    def parar(self) -> None:
        self._parar.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _escutar(self) -> None:
        user32 = _user32()
        por_id = dict(enumerate(self._acoes.items(), start=1))
        registrados: list[int] = []
        try:
            for identificador, (tecla, _acao) in por_id.items():
                if not user32.RegisterHotKey(None, identificador, MOD_NOREPEAT, TECLAS[tecla]):
                    self._erro = CapturaFalhou(f"não consegui registrar {tecla}: outro programa já usa esse atalho")
                    return
                registrados.append(identificador)
            self._registrado.set()
            self._ler_mensagens(user32, por_id)
        finally:
            for identificador in registrados:
                user32.UnregisterHotKey(None, identificador)
            self._registrado.set()

    def _ler_mensagens(self, user32: ctypes.WinDLL, por_id: Mapping[int, tuple[Tecla, Callable[[], None]]]) -> None:
        """PeekMessage + sleep: deixa a thread checar o pedido de parada."""
        mensagem = wintypes.MSG()
        while not self._parar.is_set():
            if not user32.PeekMessageW(ctypes.byref(mensagem), None, 0, 0, PM_REMOVE):
                time.sleep(0.05)
                continue
            if mensagem.message == WM_HOTKEY and mensagem.wParam in por_id:
                tecla, acao = por_id[mensagem.wParam]
                try:
                    acao()
                except Exception:
                    logger.exception("atalho %s falhou", tecla)  # a escuta continua: a próxima tecla ainda deve funcionar


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
    dica = f" Janelas parecidas: {parecidas}; ajuste CAPTURA_TITULO_JANELA no .env." if parecidas else ""
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
        logger.warning("não consegui ativar DPI por monitor (erro %s); prints podem sair cortados", erro)
