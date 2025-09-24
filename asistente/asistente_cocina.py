import pyttsx3
import speech_recognition as sr
import datetime
import os.path
import pywhatkit
import yfinance as yf
import pyjokes
import webbrowser
import datetime
import wikipedia
import requests
import threading
import time
import os
import re

from google import genai #es el SDK que nos da google para "hablar" con gemini

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# para que no se vea la clave de la api de gemini
from dotenv import load_dotenv
load_dotenv()  # carga las variables del archivo .env


# Opciones de voz / idioma
id1 = "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0"
id2 = "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0"
id3 = "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_ES-ES_HELENA_11.0"

# Permisos de Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]

archivo_lista = "lista_compras.txt"

# Diccionario para temporizadores activos
timers = {}

# Estado global (por defecto arranca en principiante)
modo = "principiante"

# Escuchar nuestro microfono y devolver el audio como texto
def transformar_audio_texto():
    # Almacenar recognizer en variable
    r = sr.Recognizer()

    # Configurar el microfono
    with sr.Microphone() as origen:
        # Tiempo de espera
        r.pause_threshold = 0.8

        # Informar que comenzo la grabacion
        print("Ya puedes hablar")

        # Guardar el audio
        audio = r.listen(origen)

        try:
            # Buscar en google
            pedido = r.recognize_google(audio, language="es-ES")

            # Imprimir prueba de ingreso
            print(f"Dijiste: {pedido}")

            # Devolver pedido
            return pedido
        except sr.UnknownValueError:
            # Prueba de que no comprendió audio
            print("Ups, no entendí")
            return "Sigo esperando"
        except sr.RequestError:
            # Prueba de que no comprendió audio
            print("Ups, no hay servicio")
            return "Sigo esperando"
        except:
            # Prueba de que no comprendió audio
            print("Ups, algo ha salido mal")
            return "Sigo esperando"

# Función para que el asistente pueda ser escuchado
def hablar(mensaje):
    # Encender el motor de pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("voice", id3)

    # Pronunciar mensaje
    engine.say(mensaje)
    engine.runAndWait()


# REQUISITO 1: SUEGERENCIAS DE RECETAS CON LO QUE SE TIENE
def recetas(ingredientes):
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) #se crea un cliente (con el que se llama a gemini) y se le pasa la api (la llave para que pueda acceder


        # promt que se le envia a gemini
        prompt = f"Tengo estos ingredientes: {ingredientes}. Dame 2 recetas sencillas que pueda preparar, solo con título y breve descripción, en español. No me des introduccion, solo mencioná directamente las opciones"

        response = client.models.generate_content( # llama al modelo y genera texto. el sdk devuelve un text que contiene la salida.
            model="gemini-2.5-flash",
            contents=prompt
        )

        resultado = response.text

        #aca devuelve por consola y lo dice por vos la respuesta de gemini
        print(resultado)
        hablar("Encontré estas opciones:")
        hablar(resultado)

        # REQUISITO 2: LEER EL PASO A PASO DE ALGUNA RECETA
        hablar("Querés que te lea los pasos de alguna receta?")
        decisionPasos = transformar_audio_texto().lower() # lee la respuesta del usuario y lo guarda en la variable decision para analizar

        if "sí" in decisionPasos or "si" in decisionPasos:
            hablar("¿De cuál receta? Podés decir primera o segunda.")
            primeraOsegunda = transformar_audio_texto().lower() # de nuevo lee lo que dijimos. en este caso si dijimos "primera" o "segunda" de las recetas

            # evalua la respuesta y la guarda en una variable
            if "primera" in primeraOsegunda:
                recetaElegida = "la primer receta"
            elif "segunda" in primeraOsegunda:
                recetaElegida = "la segunda receta"
            else:
                hablar("No entendí tu elección.")
                return

            # prompt para pedir pasos detallados a gemini segun la receta que eligio el usuario
            promptPasosReceta = f"Dame los pasos detallados para preparar {recetaElegida} usando {ingredientes}, en español."

            responsePasosReceta = client.models.generate_content( # de nuevo llama al modelo y genera texto. el sdk devuelve un text que contiene la salida.
                model = "gemini-2.5-flash",
                contents = promptPasosReceta
            )

            pasos = responsePasosReceta.text

            # muestra en consola y los lee
            print(pasos)
            hablar(pasos)

        else:
            hablar("Perfecto, me avisas si querés más detalles después.")


    except Exception as e: # captura errores. imprime el error y avisa por voz.
        print("Error al consultar Gemini:", e)
        hablar("Perdón, no pude obtener recetas en este momento.")

# REQUISITO 3: LISTA DE COMPRAS
def agregar_lista(ingredientes):
    if not ingredientes:
        hablar("No entendí el ingrediente")
        return
    with open(archivo_lista, "a", encoding="utf-8") as f:
        f.write(ingredientes + "\n")
    hablar(f"Agregado a la lista: {ingredientes}")
    print(f"Agregado a la lista: {ingredientes}")

def leer_lista():
    if not os.path.exists(archivo_lista):
        hablar("La lista de compras está vacía")
        return
    with open(archivo_lista, "r", encoding="utf-8") as f:
        lineas = [linea.strip() for linea in f.readlines() if linea.strip()]
    if not lineas:
        hablar("La lista de compras está vacía")
        return
    hablar("Tu lista de compras es:")
    for i, linea in enumerate(lineas, start=1):
        hablar(f"{i}. {linea}")
        print(f"{i}. {linea}")

# REQUISITO 4: PLANIFICADOR DE MENÚ SEMANAL
def get_calendar_service(): #maneja autenticación y devuelve el cliente de Calendar.
    creds = None #Sirve para guardar las credenciales de Google (los permisos para usar Calendar).
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        #Si ya existe el archivo token.json (que se crea después del primer login con Google),
        #se cargan las credenciales desde ahí.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)
    #opciones por si el token expiró.
def crear_evento_menu(dia, comida): #agenda un menú como evento.
    service = get_calendar_service() #Pide un servicio autenticado de Calendar para trabajar.
    hoy = datetime.date.today()
    dias_semana = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
    }
    #Define el día actual y un diccionario que asigna cada día de la semana a un número
    #Esto sirve para calcular la fecha exacta en la que cae “viernes” o “martes” de la semana actual.
    if dia not in dias_semana:
        hablar("No entendí el día que dijiste")
        return

    fecha_evento = hoy + datetime.timedelta(days=(dias_semana[dia] - hoy.weekday()) % 7)
    #Calcula la fecha del próximo día pedido.
    inicio = datetime.datetime.combine(fecha_evento, datetime.time(13, 0))
    fin = inicio + datetime.timedelta(hours=1)
    #Define el horario del evento

    evento = {
        "summary": f"Menú del día: {comida}",
        "start": {"dateTime": inicio.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
        "end": {"dateTime": fin.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
    }

    service.events().insert(calendarId="primary", body=evento).execute()
    #Inserta el evento en el calendario principal de la cuenta de Google del usuario.
    hablar(f"Agendé {comida} para el {dia} en Google Calendar")
    #Confirma por voz que se agendó.

def consultar_menu_hoy(): #lee el primer evento próximo y lo dice en voz alta.
    service = get_calendar_service()
    ahora = datetime.datetime.utcnow().isoformat() + "Z"
    #Obtiene el servicio autenticado y guarda la hora actual en formato UTC (con Z al final,
    #que significa “tiempo universal”).
    eventos = service.events().list(
        calendarId="primary", timeMin=ahora,
        maxResults=5, singleEvents=True,
        orderBy="startTime"
    ).execute().get("items", [])
    #Le pide a Google Calendar una lista de próximos eventos
    if not eventos:
        hablar("No encontré menús agendados")
    else:
        for e in eventos:
            hablar(f"Tienes {e['summary']} el {e['start'].get('dateTime', e['start'].get('date'))}")
            break
    #Si encontró eventos:
    #Lee el título (summary) y la fecha/hora (start) del primero.
    #Usa break porque solo lee uno, no todos.

#REQUISITO 5: TIPS DE COCINA
def tips_cocina(pregunta): # esta funcion funciona igual que la del requisito 1 ya que utiliza gemini
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        prompt = f"Sos un experto en cocina. Responde de manera clara, breve y en español a esta consulta: {pregunta}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        resultado = response.text
        print(resultado)
        hablar(resultado)

    except Exception as e:
        print("Error al consultar Gemini:", e)
        hablar("Perdón, no pude obtener la información en este momento.")

# REQUISITO 6: TEMPORIZADOR
def iniciar_temporizador(nombre, minutos): # Función para INICIAR un temporizador
    # Función interna que se ejecuta cuando el temporizador termine
    def alerta():
        hablar(f"¡Tiempo cumplido para {nombre}!")

    # Convertir los minutos a segundos
    segundos = minutos * 60

    # Crear un hilo/temporizador que, después de 'segundos', llame a la función alerta()
    t = threading.Timer(segundos, alerta)

    # Iniciar el temporizador (arranca el conteo en segundo plano)
    t.start()

    # Guardar en el diccionario la hora de finalización (time.time() + segundos)
    # y el objeto Timer por si después queremos consultar o cancelar
    timers[nombre] = (time.time() + segundos, t)

    # Avisar al usuario por voz que el temporizador arrancó
    hablar(f"Temporizador de {minutos} minutos iniciado para {nombre}")

# Función para CONSULTAR un temporizador
def consultar_temporizador(nombre):
    # Verificar si existe un temporizador con ese nombre
    if nombre in timers:
        # Recuperar la hora de finalización y el objeto Timer
        fin, _ = timers[nombre]

        # Calcular cuánto tiempo queda (en segundos)
        restante = int(fin - time.time())

        if restante > 0:
            # Si todavía queda tiempo, se informa minutos y segundos restantes
            hablar(f"Quedan {restante // 60} minutos y {restante % 60} segundos para {nombre}")
        else:
            # Si ya pasó el tiempo, se avisa que terminó
            hablar("Ese temporizador ya terminó")
    else:
        # Si no se encuentra ningún temporizador con ese nombre
        hablar("No encontré un temporizador con ese nombre")

# REQUISITO 8: MODO CHEF PRO
def cambiar_modo(nuevo_modo):
    global modo
    modo = nuevo_modo
    hablar(f"Modo {modo} activado")

# Explicar pasos según el modo
def explicar(texto):
    if modo == "principiante":
        # Explicación detallada
        hablar(f"{texto}. Te recomiendo hacerlo con cuidado. Si querés, te doy más detalles.")
    else:
        # Explicación más técnica y directa
        hablar(texto)


# Función central del asistente
def centro_pedido():
    # Variable de corte
    comenzar = True

    while comenzar:
        # Activar el micrófono y guardar el pedido en un String
        pedido = transformar_audio_texto().lower()

        print(f"Comando recibido: {pedido}")

        # para el requisito 1 y 2:
        if "qué puedo hacer" in pedido or "qué cocino" in pedido or "tengo" in pedido:

            # intenta extraer los ingredientes que se mencionan quitando el texto fijo (el "que puedo hacer", "tengo", del if). etso lo hace la funcion replace
            ingredientes = pedido.replace("qué puedo hacer", "").replace("qué cocino", "").replace("tengo", "").replace("con", "").strip()

            hablar(f"Buscando receta con {ingredientes}")

            recetas(ingredientes)  # llama la funcion recetas y le pasa los ingredientes
            continue

        # para el requisito 3:
        elif ("agrega" in pedido or "agregá" in pedido or "agregar" in pedido) and "lista" in pedido:
            ingredientes = (
                pedido.replace("agregar", "").replace("agregá", "").replace("a la lista de compras", "").replace("a la lista", "").replace("lista de compras", "").replace("lista", "").strip())
            if ingredientes:
                agregar_lista(ingredientes)
            else:
                hablar("No entendí los ingredientes, probá de nuevo")
                continue
        elif any(p in pedido for p in ["leer", "mostrar", "lee"]) and "lista" in pedido:
            leer_lista()
            continue


        # para el requisito 4:
        elif "agendar" in pedido:
            palabras = pedido.split()
            if "el" in palabras:
                idx = palabras.index("el")
                comida = " ".join(palabras[1:idx])
                dia = palabras[idx + 1]
                crear_evento_menu(dia, comida)
            else:
                hablar("Decime el día después de la palabra 'el'")
            continue

        elif "qué tenía para hoy" in pedido or "que tenia para hoy" in pedido:
            consultar_menu_hoy()
            continue

        # para el requisito 5:
        elif any(p in pedido for p in ["tip", "consejo", "ayuda", "reemplazar", "cuánto", "como hago"]) or "no tengo" in pedido:
            hablar("Déjame pensar…")
            tips_cocina(pedido)
            continue

        # para el requisito 6:
        elif "temporizador" in pedido and ("minuto" in pedido or "minutos" in pedido):
            palabras = pedido.split()

            # buscar número de minutos
            for p in palabras:
                if p.isdigit():
                    minutos = int(p)
                    break
            else:
                minutos = 1  # valor por defecto

            # buscar un nombre opcional para el temporizador
            if "para" in palabras:
                idx = palabras.index("para")
                nombre = " ".join(palabras[idx+1:])
            else:
                nombre = "cocina"

            iniciar_temporizador(nombre, minutos)
            continue

        elif "cuánto falta" in pedido or "cuanto falta" in pedido:
            palabras = pedido.split()
            if "para" in palabras:
                idx = palabras.index("para")
                nombre = " ".join(palabras[idx+1:])
            else:
                nombre = "cocina"
            consultar_temporizador(nombre)
            continue

        # para el requsito 8:
        elif "modo chef pro" in pedido:
            cambiar_modo("chef pro")
            continue

        elif "modo principiante" in pedido:
            cambiar_modo("principiante")
            continue


        elif "adiós" in pedido or "chau" in pedido or "salir" in pedido:
            hablar(f"Nos vemos, avisame si necesitas otra cosa")
            break

centro_pedido()