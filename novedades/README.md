# Publicar novedades en las fichas de Google

Escribes las novedades en una hoja de Google Sheets. Cada mañana GitHub
publica automáticamente las que tocan en tus fichas de Google Business Profile
(las de Google Maps) y anota en la hoja si salió bien.

## Cómo se usa (cuando ya está configurado)

Crea una Google Sheet con una pestaña llamada **Novedades**. La primera fila
debe tener exactamente estas columnas:

| fecha | texto | imagen_url | boton | enlace | fichas | estado |
|---|---|---|---|---|---|---|
| 2026-10-20 | ¿Te has quedado fuera de casa? Abrimos puertas 24h sin romper la cerradura. | https://…/foto.jpg | LLAMAR | | TODAS | |
| 2026-10-27 | Cambia tu bombín por uno antibumping con un 15% de descuento este mes. | | MAS_INFO | https://tuweb.com/ofertas | 1234567890, 9876543210 | |

- **fecha**: día a partir del cual se publica (formato `AAAA-MM-DD`). Si la
  dejas vacía, se publica en la próxima ejecución.
- **texto**: el contenido de la novedad (máximo 1500 caracteres).
- **imagen_url**: opcional. Enlace público a una foto (JPG o PNG).
- **boton**: opcional. `LLAMAR`, `MAS_INFO`, `RESERVAR`, `PEDIR`, `COMPRAR` o
  `REGISTRARSE`.
- **enlace**: la web a la que lleva el botón (no hace falta con `LLAMAR`).
- **fichas**: `TODAS` (o vacío) para publicar en todas tus fichas, o las
  zonas separadas por comas (`Leganés, Chamberí`), tal como aparecen en la
  pestaña **Fichas** (ver abajo). También vale el número de la ficha.
- **estado**: **déjalo vacío**. El sistema escribe `publicado 2026-10-20` o el
  error. Si quieres volver a publicar una fila, borra su estado.

### Pestaña Fichas

Varias fichas tienen el mismo nombre (por ejemplo, "Cerrajero Turbo 24 horas"
en Móstoles, Chamartín y Chamberí), así que el sistema las distingue por su
número. Crea una segunda pestaña llamada **Fichas** con las columnas
`zona | id | nombre` y rellena el `id` de cada zona una sola vez. Los números
salen al lanzar el modo `fichas` (ver abajo).

### Plantillas listas para importar

- [`plantilla-fichas.csv`](plantilla-fichas.csv): las 8 fichas con el `id`
  vacío, para que lo rellenes.
- [`plantilla-novedades.csv`](plantilla-novedades.csv): 32 novedades, 4 por
  ficha y una por semana, del 26 de octubre al 20 de noviembre de 2026.

Para importarlas en Google Sheets: **Archivo → Importar → Subir**, elige el
CSV y luego **Insertar hojas nuevas**. Después cambia el nombre de cada
pestaña a `Novedades` y `Fichas`.

**Ojo con las fechas:** la primera vez que funcione, se publican de golpe
todas las novedades cuya fecha ya haya pasado. Si Google tarda en aprobar el
acceso, mueve antes las fechas hacia delante. Revisa también que cada
servicio anunciado se presta de verdad en esa zona.

Para publicar en ese momento sin esperar a la mañana: en GitHub, ve a
**Actions → Publicar novedades → Run workflow** y elige:

- `publicar`: publica lo pendiente.
- `prueba`: muestra lo que publicaría, pero sin publicar nada.
- `fichas`: lista tus fichas con su número, nombre y dirección (así
  distingues las que se llaman igual), para rellenar la pestaña `Fichas`.

## Configuración inicial (una sola vez)

Una "API" es la vía por la que un programa habla con Google en tu nombre.
Hay que pedirle permiso a Google y luego darle a GitHub unas claves.

### 1. Crear un proyecto en Google Cloud

1. Entra en <https://console.cloud.google.com> con la cuenta de Google que
   gestiona tus fichas.
2. Arriba, selector de proyectos → **Proyecto nuevo** → ponle, por ejemplo,
   `novedades-fichas` → **Crear**.
3. Anota el **número de proyecto** (aparece en el panel principal).

### 2. Solicitar acceso a la API de Business Profile

Google no da acceso automáticamente: hay que pedirlo.

1. Rellena el formulario <https://support.google.com/business/contact/api_default>
   y elige **Application for Basic API Access**. Indica el número de proyecto
   del paso 1 y explica que es para publicar novedades en tus propias fichas.
2. Google suele responder por correo en unos días. Hasta que lo aprueben,
   el sistema dará error 403 o "quota 0" al publicar.

### 3. Activar las APIs

En la consola de Google Cloud, menú **APIs y servicios → Biblioteca**. Busca y
pulsa **Habilitar** en cada una:

- Google My Business API
- My Business Account Management API
- My Business Business Information API
- Google Sheets API

### 4. Crear las credenciales

1. **APIs y servicios → Pantalla de consentimiento de OAuth**: tipo
   **Externo**, nombre de la app `Novedades`, tu correo, y guarda. En
   **Usuarios de prueba**, añade tu propio correo. Después, en
   **Estado de publicación**, pulsa **Publicar aplicación**. Si la dejas en
   "Prueba", la clave del paso 5 caduca a los 7 días.
2. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de
   OAuth**. Tipo **Aplicación web**. En **URI de redirección autorizados**
   añade `https://developers.google.com/oauthplayground`. Crea y guarda el
   **ID de cliente** y el **secreto de cliente**.

### 5. Obtener la clave permanente (refresh token)

Puedes hacerlo desde el navegador del móvil:

1. Abre <https://developers.google.com/oauthplayground>.
2. Pulsa el engranaje ⚙️ (arriba a la derecha) → marca **Use your own OAuth
   credentials** → pega el ID y el secreto del paso 4.
3. A la izquierda, en el cuadro de abajo **Input your own scopes**, pega:
   ```
   https://www.googleapis.com/auth/business.manage https://www.googleapis.com/auth/spreadsheets
   ```
   y pulsa **Authorize APIs**. Entra con tu cuenta y acepta. Si sale el aviso
   de "app no verificada", pulsa **Configuración avanzada → Ir a Novedades**:
   la app es tuya.
4. Pulsa **Exchange authorization code for tokens** y copia el
   **Refresh token**.

### 6. Guardar las claves en GitHub

En este repositorio de GitHub: **Settings → Secrets and variables → Actions →
New repository secret**. Crea estos cuatro:

| Nombre | Valor |
|---|---|
| `GOOGLE_CLIENT_ID` | ID de cliente (paso 4) |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente (paso 4) |
| `GOOGLE_REFRESH_TOKEN` | Refresh token (paso 5) |
| `SHEET_ID` | El id de tu hoja: en la URL `docs.google.com/spreadsheets/d/`**`ESTE_TEXTO`**`/edit` |

### 7. Probar

**Actions → Publicar novedades → Run workflow** con `fichas`: deberías ver
tus fichas. Después lánzalo con `prueba` y, si todo cuadra, con `publicar`.

## Problemas frecuentes

- **403 / PERMISSION_DENIED / quota**: Google aún no ha aprobado el acceso
  (paso 2) o falta habilitar alguna API (paso 3).
- **invalid_grant**: la clave ha caducado. Comprueba que la app está en
  "Producción" (paso 4.1) y repite el paso 5.
- **Faltan columnas en la hoja**: revisa que la primera fila de la pestaña
  `Novedades` tenga exactamente los nombres de la tabla de arriba.
- **La foto no se publica**: el enlace debe ser público y llevar directamente
  a la imagen (Google necesita, como mínimo, 250×250 píxeles).
