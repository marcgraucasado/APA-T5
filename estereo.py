"""
estereo.py

Alumno: Marc Grau Casado

Este fichero contiene funciones para trabajar con ficheros WAVE PCM:
- conversión de estéreo a mono,
- creación de una señal estéreo a partir de dos señales mono,
- codificación de una señal estéreo de 16 bits en una señal mono de 32 bits,
- decodificación de esa señal mono de 32 bits para recuperar el estéreo.

Sólo se utiliza el módulo struct para leer y escribir datos binarios.
"""

import struct


def _lee_wave(nombre):
    """Lee un fichero WAVE PCM y devuelve su cabecera y sus muestras."""
    with open(nombre, "rb") as fichero:
        riff = fichero.read(12)

        if len(riff) != 12:
            raise ValueError("El fichero no contiene una cabecera RIFF válida")

        chunk_id, chunk_size, formato = struct.unpack("<4sI4s", riff)

        if chunk_id != b"RIFF" or formato != b"WAVE":
            raise ValueError("El fichero no tiene formato WAVE")

        fmt = None
        datos = None

        while True:
            cabecera_cacho = fichero.read(8)

            if len(cabecera_cacho) == 0:
                break

            if len(cabecera_cacho) != 8:
                raise ValueError("Cacho WAVE incompleto")

            nombre_cacho, tamanyo_cacho = struct.unpack("<4sI", cabecera_cacho)
            contenido = fichero.read(tamanyo_cacho)

            if len(contenido) != tamanyo_cacho:
                raise ValueError("Datos incompletos en el fichero WAVE")

            if nombre_cacho == b"fmt ":
                if tamanyo_cacho < 16:
                    raise ValueError("El cacho fmt no tiene el tamaño correcto")

                fmt = struct.unpack("<HHIIHH", contenido[:16])

            elif nombre_cacho == b"data":
                datos = contenido

            if tamanyo_cacho % 2 == 1:
                fichero.read(1)

        if fmt is None or datos is None:
            raise ValueError("El fichero WAVE no contiene fmt o data")

        audio_format, canales, frecuencia, byte_rate, block_align, bits = fmt

        if audio_format != 1:
            raise ValueError("Sólo se admiten ficheros PCM lineales")

        if bits not in (16, 32):
            raise ValueError("Sólo se admiten muestras de 16 o 32 bits")

        bytes_muestra = bits // 8

        if len(datos) % bytes_muestra != 0:
            raise ValueError("El tamaño de data no coincide con el formato")

        formato_muestra = "h" if bits == 16 else "i"
        num_muestras = len(datos) // bytes_muestra
        muestras = struct.unpack("<" + formato_muestra * num_muestras, datos)

        return {
            "canales": canales,
            "frecuencia": frecuencia,
            "bits": bits,
            "muestras": muestras,
        }


def _escribe_wave(nombre, canales, frecuencia, bits, muestras):
    """Escribe un fichero WAVE PCM a partir de sus datos básicos."""
    if bits not in (16, 32):
        raise ValueError("Sólo se pueden escribir muestras de 16 o 32 bits")

    formato_muestra = "h" if bits == 16 else "i"
    datos = struct.pack("<" + formato_muestra * len(muestras), *muestras)

    bytes_muestra = bits // 8
    block_align = canales * bytes_muestra
    byte_rate = frecuencia * block_align
    tamanyo_data = len(datos)
    tamanyo_riff = 36 + tamanyo_data

    with open(nombre, "wb") as fichero:
        fichero.write(struct.pack("<4sI4s", b"RIFF", tamanyo_riff, b"WAVE"))

        fichero.write(struct.pack("<4sI", b"fmt ", 16))
        fichero.write(struct.pack(
            "<HHIIHH",
            1,
            canales,
            frecuencia,
            byte_rate,
            block_align,
            bits,
        ))

        fichero.write(struct.pack("<4sI", b"data", tamanyo_data))
        fichero.write(datos)


def _satura_16(valor):
    """Limita un valor al rango de una muestra PCM de 16 bits."""
    return max(-32768, min(32767, valor))


def _a_entero_16(valor):
    """Convierte los 16 bits menos significativos en entero con signo."""
    return valor - 65536 if valor >= 32768 else valor


def estereo2mono(ficEste, ficMono, canal=2):
    """
    Lee un fichero WAVE estéreo de 16 bits y escribe un fichero mono.

    canal=0: canal izquierdo.
    canal=1: canal derecho.
    canal=2: semisuma (L + R) / 2.
    canal=3: semidiferencia (L - R) / 2.
    """
    wave = _lee_wave(ficEste)

    if wave["canales"] != 2 or wave["bits"] != 16:
        raise ValueError("El fichero de entrada debe ser estéreo de 16 bits")

    if canal not in (0, 1, 2, 3):
        raise ValueError("El canal debe ser 0, 1, 2 o 3")

    muestras = wave["muestras"]
    pares = zip(muestras[0::2], muestras[1::2])

    if canal == 0:
        salida = muestras[0::2]
    elif canal == 1:
        salida = muestras[1::2]
    elif canal == 2:
        salida = tuple((izq + der) // 2 for izq, der in pares)
    else:
        salida = tuple((izq - der) // 2 for izq, der in pares)

    _escribe_wave(ficMono, 1, wave["frecuencia"], 16, salida)


def mono2estereo(ficIzq, ficDer, ficEste):
    """
    Lee dos ficheros WAVE mono de 16 bits y construye un fichero estéreo.
    """
    izquierdo = _lee_wave(ficIzq)
    derecho = _lee_wave(ficDer)

    if izquierdo["canales"] != 1 or derecho["canales"] != 1:
        raise ValueError("Los dos ficheros de entrada deben ser mono")

    if izquierdo["bits"] != 16 or derecho["bits"] != 16:
        raise ValueError("Los dos ficheros de entrada deben ser de 16 bits")

    if izquierdo["frecuencia"] != derecho["frecuencia"]:
        raise ValueError("Los ficheros deben tener la misma frecuencia")

    if len(izquierdo["muestras"]) != len(derecho["muestras"]):
        raise ValueError("Los ficheros deben tener el mismo número de muestras")

    salida = tuple(
        muestra
        for par in zip(izquierdo["muestras"], derecho["muestras"])
        for muestra in par
    )

    _escribe_wave(ficEste, 2, izquierdo["frecuencia"], 16, salida)


def codEstereo(ficEste, ficCod):
    """
    Codifica una señal estéreo de 16 bits en una señal mono de 32 bits.

    Los 16 bits más significativos contienen la semisuma.
    Los 16 bits menos significativos contienen la semidiferencia.
    """
    wave = _lee_wave(ficEste)

    if wave["canales"] != 2 or wave["bits"] != 16:
        raise ValueError("El fichero de entrada debe ser estéreo de 16 bits")

    muestras = wave["muestras"]

    codificadas = tuple(
        (((izq + der) // 2) << 16) | (((izq - der) // 2) & 0xFFFF)
        for izq, der in zip(muestras[0::2], muestras[1::2])
    )

    _escribe_wave(ficCod, 1, wave["frecuencia"], 32, codificadas)


def decEstereo(ficCod, ficEste):
    """
    Decodifica una señal mono de 32 bits y reconstruye una señal estéreo.
    """
    wave = _lee_wave(ficCod)

    if wave["canales"] != 1 or wave["bits"] != 32:
        raise ValueError("El fichero de entrada debe ser mono de 32 bits")

    pares = (
        (
            _satura_16((muestra >> 16) + _a_entero_16(muestra & 0xFFFF)),
            _satura_16((muestra >> 16) - _a_entero_16(muestra & 0xFFFF)),
        )
        for muestra in wave["muestras"]
    )

    salida = tuple(valor for par in pares for valor in par)

    _escribe_wave(ficEste, 2, wave["frecuencia"], 16, salida)