from robodk import robolink     # RoboDK API
from robodk import robomath     # Robot toolbox
import threading                #Libreria de hilos
import time                     #Libreria de para usar sleeps
import paho.mqtt.client as mqtt #Libreria para la conexion con mqtt
RDK = robolink.Robolink()       #Conexión con RoboDK


INCREMENTO_TAPA = 330
INCREMENTO_MM = 1300
INCREMENTO_M = 1300
CREACION_TARTAS = 1300
cinta = RDK.Item('Cinta')
tarta = RDK.Item('tarta')
tapa1 = RDK.Item('tapa1')
tapa2 = RDK.Item('tapa2')
tapa3 = RDK.Item('tapa3')
tapa4 = RDK.Item('tapa4')
tapa5 = RDK.Item('tapa5')
tapa6 = RDK.Item('tapa6')
conjunto = RDK.Item('conjunto')
piston1 = RDK.Item('Piston1')
piston2 = RDK.Item('Piston2')
sensor = RDK.Item('Sensor')
sensor2 = RDK.Item('Sensor2')
sensor3 = RDK.Item('Sensor3')
sistRefCinta=RDK.Item('FrameTarta')
sistRefCinta2=RDK.Item('FrameTapa')
cinta2 = RDK.Item('Cinta2')
robot = RDK.Item('Robot1')
robot_2 = RDK.Item('UR5')
frame_pick = RDK.Item('Cinta3', robolink.ITEM_TYPE_FRAME)
frame_piston1 = RDK.Item('FramePiston1', robolink.ITEM_TYPE_FRAME)
frame_piston2 = RDK.Item('FramePiston2', robolink.ITEM_TYPE_FRAME)
frame_place = RDK.Item('FramePlace', robolink.ITEM_TYPE_FRAME)
frame_topping = RDK.Item('FrameTopping', robolink.ITEM_TYPE_FRAME)
frame_robot = RDK.Item('FrameRobot', robolink.ITEM_TYPE_FRAME)
target_prepick = RDK.Item('PrePick2', robolink.ITEM_TYPE_TARGET)
target_final1 = RDK.Item('Final1', robolink.ITEM_TYPE_TARGET)
target_inicio1 = RDK.Item('Inicio1', robolink.ITEM_TYPE_TARGET)
target_inicio2 = RDK.Item('Inicio2', robolink.ITEM_TYPE_TARGET)
target_final2 = RDK.Item('Final2', robolink.ITEM_TYPE_TARGET)

sensor_esp_activado = False
estacion_pausada = False
lista = [tarta]
lista2 = [tapa6, tapa5, tapa4, tapa3, tapa2, tapa1]
detectado = False
senyal = False
senyal2 = False
lista3 = [conjunto]
ntarta = 0
ntapa = 0
i = 0
j = 0
x = 1

evento_iniciar = threading.Event()
evento_terminado = threading.Event()    
lock = threading.Lock()     
def mover_robot(nombre_proceso):
    RDK_hilo = robolink.Robolink()
    while True:
        evento_iniciar.wait()        # Espera bloqueado hasta que se active
        evento_iniciar.clear()       # Lo resetea
        
        p = RDK_hilo.Item(nombre_proceso, robolink.ITEM_TYPE_PROGRAM)
        p.RunProgram()
        p.WaitFinished()
        
        evento_terminado.set()       # Avisa al bucle principal



hilo_robot = threading.Thread(target=mover_robot, args=("Topping",))
hilo_robot.start()

def on_message(client, userdata, msg):
    global sensor_esp_activado, estacion_pausada
    payload = msg.payload.decode("utf-8")
    
    # 1. Comportamiento del Botón (Interrupción inmediata)
    if payload == "EMERGENCY":
        with lock:
            if not estacion_pausada:
                RDK_btn = robolink.Robolink()
                RDK_btn.setSimulationSpeed(0)
                estacion_pausada = True
            else:
                # Si volvemos a recibir EMERGENCY estando pausados, actuamos como EMERGENCY_OFF
                RDK_btn = robolink.Robolink()
                RDK_btn.setSimulationSpeed(5)
                estacion_pausada = False

    elif payload == "EMERGENCY_OFF":
        with lock:
            if estacion_pausada:
                print("[SISTEMA] Señal de rearme recibida. Reanudando estación...\n")
                RDK_btn = robolink.Robolink()
                RDK_btn.setSimulationSpeed(5)
                estacion_pausada = False
        
    # 2. Comportamiento del Nuevo Sensor (Actualiza la bandera)
    elif payload == "EMPTY":
        with lock:
            sensor_esp_activado = True

# --- CONFIGURACIÓN --- 
broker_address = "broker.emqx.io"
port = 1883
password = "joseba00"
topic = "giirob/pr2/estacion/leds"
#user = "Iphone Joseba"


client = mqtt.Client()
client.connect(broker_address, 1883, 60)
client.subscribe(topic)
client.on_message = on_message
client.loop_start()
time.sleep(1)



def enviar_mensaje(cliente, mensaje):
    resultado = cliente.publish(topic, mensaje)
    resultado.wait_for_publish()

enviar_mensaje(client, "READY")
time.sleep(2.0)
enviar_mensaje(client, "READY_OFF")

while True:
    if j == 4 * x:

        enviar_mensaje(client, "FULL")

        with lock:
            sensor_esp_activado = False
            
        # Espera activa del sensor
        esperando_sensor = True
        while esperando_sensor:
            with lock:
                if sensor_esp_activado:
                    esperando_sensor = False 
            robomath.pause(0.1)

        lista3[j - 1].setVisible(False)
        lista3[j - 2].setVisible(False)
        lista3[j - 3].setVisible(False)
        lista3[j - 4].setVisible(False)
        x += 1
        enviar_mensaje(client, "EMPTY")
    detectado = False
    senyal = False
    for item in lista:
        if detectado == False and senyal == False:
            detectado = sensor.Collision(item)
            senyal = sensor2.Collision(item)
        if detectado == True and senyal == False:
            senyal = sensor2.Collision(item)
        if detectado == False and senyal == True:
            detectado = sensor.Collision(item)
        robomath.pause(0.01)

    

    if detectado == True and senyal == False:
        enviar_mensaje(client, "S1_ON")
        if cinta.Valid():
            p = RDK.Item('Topping', robolink.ITEM_TYPE_PROGRAM)
            p.RunProgram()
            p.WaitFinished()
            #cinta.MoveJ(cinta.Joints() + INCREMENTO_M)
            tarta.Copy()
            tartaCopia=RDK.Paste(sistRefCinta)
            tartaCopia.setName('tarta')
            ntarta=ntarta + 1
            tartaCopia.setPose(tarta.Pose()*robomath.transl(0,0,-CREACION_TARTAS*ntarta))
            tartaCopia.setVisible(True)
            RDK.setParam('num_tartas', ntarta)
            lista.append(tartaCopia)
        enviar_mensaje(client, "S1_OFF")
    if detectado == False and senyal == True:
        enviar_mensaje(client, "S2_ON")
        for item2 in lista2:
            senyal2 = sensor3.Collision(item2)
            robomath.pause(0.01)
        p = RDK.Item('PickandPlace', robolink.ITEM_TYPE_PROGRAM)
        p.RunProgram()
        p.WaitFinished()
        piston1.MoveJ(target_final1)
        piston1.MoveJ(target_inicio1)
        piston2.MoveJ(target_final2)
        piston2.MoveJ(target_inicio2)
        cinta2.MoveJ(cinta2.Joints() + INCREMENTO_TAPA)
        tapa1.Copy()
        tapaCopia=RDK.Paste(sistRefCinta2)
        tapaCopia.setName('tapaC')
        ntapa=ntapa + 1
        tapaCopia.setPose(robomath.transl(-INCREMENTO_TAPA*ntapa,0,0))
        tapaCopia.setVisible(True)
        RDK.setParam('num_tapas', ntapa)
        lista2.append(tapaCopia)
        lista[0 + i].setVisible(False)
        lista2[0 + i].setVisible(False)
        conjunto.Copy()
        conjuntoCopia=RDK.Paste(frame_place)
        conjuntoCopia.setName('conjuntoC')
        conjuntoCopia.setPose(robomath.transl(20, 0, -10))
        lista3.append(conjuntoCopia)
        conjuntoCopia.setVisible(False)
        lista3[0 + j].setVisible(True)
        p = RDK.Item('PickandPlace2', robolink.ITEM_TYPE_PROGRAM)
        p.RunProgram()
        p.WaitFinished()
        j = j + 1
        i = i + 1
        enviar_mensaje(client, "S2_OFF")
        cinta.MoveJ(cinta.Joints() + INCREMENTO_M)
    if detectado == True and senyal == True:
        enviar_mensaje(client, "S1_ON")   
        enviar_mensaje(client, "S2_ON")
        evento_terminado.clear()     # Limpia antes de lanzar
        evento_iniciar.set()  
        p2 = RDK.Item('PickandPlace', robolink.ITEM_TYPE_PROGRAM)
        p2.RunProgram()
        p2.WaitFinished()
        piston1.MoveJ(target_final1)
        piston1.MoveJ(target_inicio1)
        piston2.MoveJ(target_final2)
        piston2.MoveJ(target_inicio2)
        cinta2.MoveJ(cinta2.Joints() + INCREMENTO_TAPA)
        tapa1.Copy()
        tapaCopia=RDK.Paste(sistRefCinta2)
        tapaCopia.setName('tapaC')
        ntapa=ntapa + 1
        tapaCopia.setPose(robomath.transl(-INCREMENTO_TAPA*ntapa,0,0))
        tapaCopia.setVisible(True)
        RDK.setParam('num_tapas', ntapa)
        lista2.append(tapaCopia)
        lista[0 + i].setVisible(False)
        lista2[0 + i].setVisible(False)
        conjunto.Copy()
        conjuntoCopia=RDK.Paste(frame_place)
        conjuntoCopia.setName('conjuntoC')
        conjuntoCopia.setPose(robomath.transl(20, 0, -10))
        lista3.append(conjuntoCopia)
        conjuntoCopia.setVisible(False)
        lista3[0 + j].setVisible(True)
        p3 = RDK.Item('PickandPlace2', robolink.ITEM_TYPE_PROGRAM)
        p3.RunProgram()
        p3.WaitFinished()
        evento_terminado.wait() 
        tarta.Copy()
        tartaCopia=RDK.Paste(sistRefCinta)
        tartaCopia.setName('tarta')
        ntarta=ntarta + 1
        j = j + 1
        i = i + 1
        #cinta.MoveJ(cinta.Joints() + INCREMENTO_M)
        tartaCopia.setPose(tarta.Pose()*robomath.transl(0,0,-CREACION_TARTAS*ntarta))
        tartaCopia.setVisible(True)
        RDK.setParam('num_tartas', ntarta)
        lista.append(tartaCopia)
        enviar_mensaje(client, "S1_OFF")   
        enviar_mensaje(client, "S2_OFF")
    cinta.MoveJ(cinta.Joints() + INCREMENTO_M)

    detectado = False
    



