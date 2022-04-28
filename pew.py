from micropython import const
import board
import busio
import displayio
import pwmio
import time
import touchio


_FONT = (
    b'{{{{{{wws{w{HY{{{{YDYDY{sUtGUsH[wyH{uHgHE{ws{{{{vyxyv{g[K[g{{]f]{{{wDw{{'
    b'{{{wy{{{D{{{{{{{w{K_w}x{VHLHe{wuwww{`KfyD{UKgKU{w}XDK{DxTKT{VxUHU{D[wyx{'
    b'UHfHU{UHEKe{{w{w{{{w{wy{KwxwK{{D{D{{xwKwx{eKg{w{VIHyB{fYH@H{dHdHd{FyxyF{'
    b'`XHX`{DxtxD{Dxtxx{FyxIF{HHDHH{wwwww{KKKHU{HXpXH{xxxxD{Y@DLH{IL@LX{fYHYf{'
    b'`HH`x{fYHIF{`HH`H{UxUKU{Dwwww{HHHIR{HHH]w{HHLD@{HYsYH{HYbww{D[wyD{txxxt{'
    b'x}w_K{GKKKG{wLY{{{{{{{{Dxs{{{{{BIIB{x`XX`{{ByyB{KBIIB{{WIpF{OwUwww{`YB[`'
    b'x`XHH{w{vwc{K{OKHUxHpXH{vwws_{{dD@H{{`XHH{{fYYf{{`XX`x{bYIBK{Ipxx{{F}_d{'
    b'wUws_{{HHIV{{HH]s{{HLD@{{HbbH{{HHV[a{D_}D{Cw|wC{wwwwwwpwOwp{WKfxu{@YYY@{'
)
_SALT = const(132)
_PATTERNS = (
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x44\x11\x44\x11\x44\x11\x44\x11\x44\x11',
#    b'\xee\xbb\xee\xbb\xee\xbb\xee\xbb\xee\xbb',
    b'\x55\xaa\x55\xaa\x55\xaa\x55\xaa\x55\xaa',
    b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff',
)

K_UP = 0x01
K_DOWN = 0x02
K_LEFT = 0x04
K_RIGHT = 0x08
K_O =0x10
K_X = 0x20

_tick = None


def brightness(level):
    _light.duty_cycle = level * 4369

def show(pix):
    pix_buffer = pix.buffer
    bus = board.DISPLAY.bus
    buffer = bytearray(80)
    for y in range(8):
        pix_index = pix.width * (7 - y) + 7
        board.DISPLAY.bus.send(0x08, b'')
        board.DISPLAY.bus.send(0x10, b'')
        index = 0
        for x in range(8):
            buffer[index:index+10] = _PATTERNS[pix_buffer[pix_index]]
            pix_index -= 1
            index += 10
        bus.send(0xb0|(y), buffer)


def keys():
    keys = 0
    for bit, touch in enumerate(_touch):
        keys <<= 1
        keys |= touch.value
    return keys


def tick(delay):
    global _tick

    now = time.monotonic()
    _tick += delay
    if _tick < now:
        _tick = now
    else:
        time.sleep(_tick - now)


class GameOver(Exception):
    pass


class Pix:
    def __init__(self, width=8, height=8, buffer=None):
        if buffer is None:
            buffer = bytearray(width * height)
        self.buffer = buffer
        self.width = width
        self.height = height

    @classmethod
    def from_text(cls, string, color=None, bgcolor=0, colors=None):
        pix = cls(4 * len(string), 6)
        font = memoryview(_FONT)
        if colors is None:
            if color is None:
                colors = (3, 2, 1, bgcolor)
            else:
                colors = (color, color, bgcolor, bgcolor)
        x = 0
        for c in string:
            index = ord(c) - 0x20
            if not 0 <= index <= 95:
                continue
            row = 0
            for byte in font[index * 6:index * 6 + 6]:
                unsalted = byte ^ _SALT
                for col in range(4):
                    pix.pixel(x + col, row, colors[unsalted & 0x03])
                    unsalted >>= 2
                row += 1
            x += 4
        return pix

    @classmethod
    def from_iter(cls, lines):
        pix = cls(len(lines[0]), len(lines))
        y = 0
        for line in lines:
            x = 0
            for pixel in line:
                pix.pixel(x, y, pixel)
                x += 1
            y += 1
        return pix

    def pixel(self, x, y, color=None):
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return 0
        if color is None:
            return self.buffer[x + y * self.width]
        self.buffer[x + y * self.width] = color

    def box(self, color, x=0, y=0, width=None, height=None):
        x = min(max(x, 0), self.width - 1)
        y = min(max(y, 0), self.height - 1)
        width = max(0, min(width or self.width, self.width - x))
        height = max(0, min(height or self.height, self.height - y))
        for y in range(y, y + height):
            xx = y * self.width + x
            for i in range(width):
                self.buffer[xx] = color
                xx += 1

    def blit(self, source, dx=0, dy=0, x=0, y=0,
             width=None, height=None, key=None):
        if dx < 0:
            x -= dx
            dx = 0
        if x < 0:
            dx -= x
            x = 0
        if dy < 0:
            y -= dy
            dy = 0
        if y < 0:
            dy -= y
            y = 0
        width = min(min(width or source.width, source.width - x),
                    self.width - dx)
        height = min(min(height or source.height, source.height - y),
                     self.height - dy)
        source_buffer = memoryview(source.buffer)
        self_buffer = self.buffer
        if key is None:
            for row in range(height):
                xx = y * source.width + x
                dxx = dy * self.width + dx
                self_buffer[dxx:dxx + width] = source_buffer[xx:xx + width]
                y += 1
                dy += 1
        else:
            for row in range(height):
                xx = y * source.width + x
                dxx = dy * self.width + dx
                for col in range(width):
                    color = source_buffer[xx]
                    if color != key:
                        self_buffer[dxx] = color
                    dxx += 1
                    xx += 1
                y += 1
                dy += 1

    def __str__(self):
        return "\n".join(
            "".join(
                ('.', '+', '*', '@')[self.pixel(x, y)]
                for x in range(self.width)
            )
            for y in range(self.height)
        )


def init():
    global _tick
    global _touch
    global _light

    if _tick is not None:
        return

#    _INIT = (
#        b'\xe2\x00' # reset
#        b'\x2f\x00' # power on
#        b'\x81\x00' # contrast
#        b'\xa4\x00' # a4 display normal
#        b'\xaf\x00' # display on
#    )
#
#    displayio.release_displays()
#    spi = busio.SPI(clock=board._SCK, MOSI=board._MOSI)
#    bus = displayio.FourWire(spi, chip_select=board._CS, baudrate=40_000_000,
#            reset=board._RST)
#    display = displayio.Display(bus, _INIT, width=96, height=68, color_depth=1,
#            data_as_commands=True, grayscale=True, SH1107_addressing=True,
#            pixels_in_byte_share_row=False, brightness=0,
#            rotation=180, auto_refresh=False)

    _light = pwmio.PWMOut(board._BL)

    buffer = b'\x00' * 96
    bus = board.DISPLAY.bus
    for y in range(9):
        bus.send(0x00, b'')
        bus.send(0x10, b'')
        bus.send(0xb0|y, buffer)
    _tick = time.monotonic()
    _touch = tuple(touchio.TouchIn(pin) for pin in (
        board._X,
        board._O,
        board._RIGHT,
        board._LEFT,
        board._DOWN,
        board._UP,
    ))
