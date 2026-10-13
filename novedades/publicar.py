"""Publica novedades en las fichas de Google Business Profile.

Lee las novedades de una Google Sheet, publica las que ya tocan en las
fichas indicadas y marca cada fila como publicada (o con el error) en la
columna "estado", para no publicar nada dos veces.

Solo usa la biblioteca estándar de Python.

Variables de entorno:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN  credenciales
  SHEET_ID     id de la hoja (lo que va entre /d/ y /edit en su URL)
  SHEET_TAB    pestaña de la hoja (por defecto "Novedades")
  FICHAS_TAB   pestaña opcional con columnas "zona" e "id" para poder
               escribir nombres de zona en la columna "fichas" (por
               defecto "Fichas")
  DRY_RUN      "1" para mostrar qué se publicaría sin publicar nada

Uso:
  python publicar.py            publica las novedades pendientes
  python publicar.py fichas     lista tus fichas y sus identificadores
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCOUNTS_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"
POSTS_API = "https://mybusiness.googleapis.com/v4"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

COLUMNAS = ["fecha", "texto", "imagen_url", "boton", "enlace", "fichas", "estado"]

# Nombre del botón en la hoja -> tipo de acción de Google.
BOTONES = {
    "": None,
    "LLAMAR": "CALL",
    "MAS_INFO": "LEARN_MORE",
    "RESERVAR": "BOOK",
    "PEDIR": "ORDER",
    "COMPRAR": "SHOP",
    "REGISTRARSE": "SIGN_UP",
}


def pedir(url, token=None, metodo="GET", datos=None):
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")
        raise RuntimeError(f"{metodo} {url} -> {e.code}: {detalle}") from None


def obtener_token():
    datos = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=datos)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"No se pudo obtener acceso a Google: {e.read().decode(errors='replace')}")


def listar_fichas(token):
    """Devuelve {"locations/123": ("accounts/456", "Nombre de la ficha")}
    y {"locations/123": "dirección"}."""
    fichas, direcciones = {}, {}
    cuentas = pedir(f"{ACCOUNTS_API}/accounts", token).get("accounts", [])
    for cuenta in cuentas:
        pagina = ""
        while True:
            url = (f"{INFO_API}/{cuenta['name']}/locations?readMask=name,title,storefrontAddress"
                   f"&pageSize=100&pageToken={pagina}")
            resp = pedir(url, token)
            for loc in resp.get("locations", []):
                fichas[loc["name"]] = (cuenta["name"], loc.get("title", ""))
                direcciones[loc["name"]] = ", ".join(
                    loc.get("storefrontAddress", {}).get("addressLines", [])
                    + [loc.get("storefrontAddress", {}).get("locality", "")]).strip(", ")
            pagina = resp.get("nextPageToken")
            if not pagina:
                break
    return fichas, direcciones


def leer_hoja(token, sheet_id, pestana):
    rango = urllib.parse.quote(f"{pestana}!A1:G")
    filas = pedir(f"{SHEETS_API}/{sheet_id}/values/{rango}", token).get("values", [])
    if not filas:
        return []
    cabecera = [c.strip().lower() for c in filas[0]]
    faltan = [c for c in COLUMNAS if c not in cabecera]
    if faltan:
        sys.exit(f"Faltan columnas en la hoja: {', '.join(faltan)}. "
                 f"La primera fila debe ser: {', '.join(COLUMNAS)}")
    novedades = []
    for num, fila in enumerate(filas[1:], start=2):
        fila = fila + [""] * (len(cabecera) - len(fila))
        novedad = {c: fila[cabecera.index(c)].strip() for c in COLUMNAS}
        novedad["_fila"] = num
        novedad["_col_estado"] = chr(ord("A") + cabecera.index("estado"))
        novedades.append(novedad)
    return novedades


def leer_zonas(token, sheet_id, pestana):
    """Devuelve {"leganés": "locations/123"} desde la pestaña de fichas."""
    rango = urllib.parse.quote(f"{pestana}!A1:C")
    try:
        filas = pedir(f"{SHEETS_API}/{sheet_id}/values/{rango}", token).get("values", [])
    except RuntimeError as e:
        if "Unable to parse range" in str(e):
            return {}  # la pestaña no existe: solo se usarán ids
        raise
    if not filas:
        return {}
    cabecera = [c.strip().lower() for c in filas[0]]
    if "zona" not in cabecera or "id" not in cabecera:
        sys.exit(f"La pestaña {pestana} debe tener las columnas: zona, id")
    zonas = {}
    for fila in filas[1:]:
        fila = fila + [""] * (len(cabecera) - len(fila))
        zona = fila[cabecera.index("zona")].strip().lower()
        ficha = fila[cabecera.index("id")].strip().removeprefix("locations/")
        if zona and ficha:
            zonas[zona] = f"locations/{ficha}"
    return zonas


def marcar_estado(token, sheet_id, pestana, novedad, estado):
    celda = urllib.parse.quote(f"{pestana}!{novedad['_col_estado']}{novedad['_fila']}")
    pedir(f"{SHEETS_API}/{sheet_id}/values/{celda}?valueInputOption=RAW", token,
          "PUT", {"values": [[estado]]})


def toca_publicar(novedad, hoy):
    if novedad["estado"] or not novedad["texto"]:
        return False
    if not novedad["fecha"]:
        return True
    try:
        return datetime.date.fromisoformat(novedad["fecha"]) <= hoy
    except ValueError:
        raise ValueError(f"fecha '{novedad['fecha']}' no válida, usa AAAA-MM-DD")


def crear_publicacion(novedad):
    if len(novedad["texto"]) > 1500:
        raise ValueError("el texto supera los 1500 caracteres que permite Google")
    boton = novedad["boton"].upper().replace(" ", "_").replace("Á", "A")
    if boton not in BOTONES:
        raise ValueError(f"botón '{novedad['boton']}' no válido, usa: "
                         + ", ".join(b for b in BOTONES if b))
    post = {"languageCode": "es", "topicType": "STANDARD", "summary": novedad["texto"]}
    if BOTONES[boton]:
        post["callToAction"] = {"actionType": BOTONES[boton]}
        if BOTONES[boton] != "CALL":
            if not novedad["enlace"]:
                raise ValueError(f"el botón {boton} necesita un enlace")
            post["callToAction"]["url"] = novedad["enlace"]
    if novedad["imagen_url"]:
        post["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": novedad["imagen_url"]}]
    return post


def destinos(novedad, fichas, zonas):
    if not novedad["fichas"] or novedad["fichas"].upper() == "TODAS":
        return list(fichas)
    elegidas = []
    for f in novedad["fichas"].replace(";", ",").split(","):
        f = f.strip()
        if f.lower() in zonas:
            nombre = zonas[f.lower()]
        elif f.removeprefix("locations/").isdigit():
            nombre = f"locations/{f.removeprefix('locations/')}"
        else:
            raise ValueError(f"zona '{f}' no está en la pestaña de fichas")
        if nombre not in fichas:
            raise ValueError(f"ficha '{f}' no encontrada en tu cuenta")
        elegidas.append(nombre)
    return elegidas


def main():
    token = obtener_token()
    fichas, direcciones = listar_fichas(token)

    if len(sys.argv) > 1 and sys.argv[1] == "fichas":
        print(f"{len(fichas)} fichas encontradas:")
        for nombre, (_, titulo) in fichas.items():
            print(f"  {nombre.removeprefix('locations/')}\t{titulo}\t{direcciones[nombre]}")
        return

    sheet_id = os.environ["SHEET_ID"]
    pestana = os.environ.get("SHEET_TAB") or "Novedades"
    zonas = leer_zonas(token, sheet_id, os.environ.get("FICHAS_TAB") or "Fichas")
    dry_run = os.environ.get("DRY_RUN") == "1"
    hoy = datetime.date.today()
    errores = 0

    for novedad in leer_hoja(token, sheet_id, pestana):
        try:
            if not toca_publicar(novedad, hoy):
                continue
            post = crear_publicacion(novedad)
            objetivos = destinos(novedad, fichas, zonas)
        except ValueError as e:
            errores += 1
            print(f"Fila {novedad['_fila']}: {e}")
            if not dry_run:
                marcar_estado(token, sheet_id, pestana, novedad, f"error: {e}")
            continue

        print(f"Fila {novedad['_fila']}: publicando en {len(objetivos)} fichas")
        fallos = []
        for nombre in objetivos:
            cuenta, titulo = fichas[nombre]
            if dry_run:
                print(f"  [prueba] {titulo}: {json.dumps(post, ensure_ascii=False)}")
                continue
            try:
                pedir(f"{POSTS_API}/{cuenta}/{nombre}/localPosts", token, "POST", post)
                print(f"  OK {titulo}")
            except RuntimeError as e:
                fallos.append(titulo or nombre)
                print(f"  ERROR {titulo}: {e}")

        if dry_run:
            continue
        if fallos:
            errores += 1
            estado = f"error en: {', '.join(fallos)}"
        else:
            estado = f"publicado {hoy.isoformat()}"
        marcar_estado(token, sheet_id, pestana, novedad, estado)

    if errores:
        sys.exit(f"{errores} novedades con errores, revisa la columna estado")


if __name__ == "__main__":
    main()
