#include <WiFi.h>
#include <PubSubClient.h>

//wifi
const char *ssid = "Iphone Joseba";
const char *password = "joseba00";

const char *mqtt_broker = "broker.emqx.io";
const int mqtt_port = 1883;

// topics según la función | dividido en los dos robots, palet y boton de emergencia
const char *topic_robot1     = "giirob/pr2/grupo04/robot1";
const char *topic_robot2     = "giirob/pr2/grupo04/robot2";
const char *topic_palet      = "giirob/pr2/grupo04/lleno_vacio";
const char *topic_emergencia = "giirob/pr2/grupo04/emergencia";

//Pines
const int LED_SENSOR1 = 13;
const int LED_SENSOR2 = 12;
const int LED_READY   = 14;
const int LED_PALET   = 15;
const int BTN_EMERGENCIA = 4;

const int PIN_TRIG = 3;
const int PIN_ECHO = 9;

// CONFIGURACIÓN DE FREERTOS
enum TipoEvento { EV_EMERGENCIA, EV_PALET_RECOGIDO };
enum EstadoSensor { SENSOR_INACTIVO, SENSOR_ACTIVO };

struct DatosTareas {
  QueueHandle_t colaEventos;      
  QueueHandle_t colaControlSensor;
};

WiFiClient espClient;
PubSubClient client(espClient);
DatosTareas* ptrDatosGlobal = NULL;

// GESTIÓN DE EVENTOS (ISR)
void IRAM_ATTR emergenciaISR() {
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;
  TipoEvento ev = EV_EMERGENCIA;
  
  xQueueSendFromISR(ptrDatosGlobal->colaEventos, &ev, &xHigherPriorityTaskWoken);
  
  if (xHigherPriorityTaskWoken) {
    portYIELD_FROM_ISR();
  }
}

//FILTRADO DE JSON
void callback(char *topic, byte *payload, unsigned int length) {
  String mensaje = "";
  for (int i = 0; i < length; i++) {
    mensaje += (char)payload[i];
  }

  Serial.print("Mensaje recibido en ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(mensaje);

  //Ignorar mensajes enviados por arduino, como emergency o empty
  if (mensaje.indexOf("EMERGENCY") >= 0 || mensaje.indexOf("EMPTY") >= 0) {
    return;
  }

  //Filtrado por topic
  if (strcmp(topic, topic_robot1) == 0) {
    if (mensaje.indexOf("ON") >= 0)  digitalWrite(LED_SENSOR1, LOW);  
    if (mensaje.indexOf("OFF") >= 0) digitalWrite(LED_SENSOR1, HIGH); 
  } 
  
  else if (strcmp(topic, topic_robot2) == 0) {
    if (mensaje.indexOf("ON") >= 0)  digitalWrite(LED_SENSOR2, LOW);
    if (mensaje.indexOf("OFF") >= 0) digitalWrite(LED_SENSOR2, HIGH);
  } 
  
  else if (strcmp(topic, topic_palet) == 0) {
    if (mensaje.indexOf("FULL") >= 0) {
      digitalWrite(LED_PALET, LOW);
      EstadoSensor orden = SENSOR_ACTIVO;
      if (ptrDatosGlobal != NULL) {
        xQueueSend(ptrDatosGlobal->colaControlSensor, &orden, 0);
      }
    }
  } 
  
  else if (strcmp(topic, topic_emergencia) == 0) {
    if (mensaje.indexOf("READY_OFF") >= 0) {
      digitalWrite(LED_READY, HIGH);
    } else if (mensaje.indexOf("READY") >= 0) {
      digitalWrite(LED_READY, LOW);
    }
  }
}

// FUNCIONES DE CONEXIÓN
void conectarWiFi() {
  Serial.println("Conectando al WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    vTaskDelay(pdMS_TO_TICKS(500));
    Serial.print(".");
  }
  Serial.println("\nWiFi Conectado");
}

void reconnect() {
  while (!client.connected()) {
    String client_id = "ESP32-Receptor-" + String(WiFi.macAddress());
    Serial.println("Conectando...");
    
    if (client.connect(client_id.c_str())) {      
      //Se ha utilizado con # para que englobe a todos los subtopics
      client.subscribe("giirob/pr2/grupo04/#"); 
      Serial.println("Suscrito con éxito");
    } else {
      Serial.print("Fallo conexión MQTT");
      vTaskDelay(pdMS_TO_TICKS(5000));
    }
  }
}

// TAREA MQTT: ENVIAR DATOS 
void tareaMQTT(void *pvParameters) {
  DatosTareas* params = (DatosTareas*) pvParameters;
  
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = pdMS_TO_TICKS(50);
  
  bool modoEmergencia = false;
  int contadorParpadeo = 0;

  conectarWiFi();
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);

  for (;;) {
    if (!client.connected()) {
      reconnect();
    }
    client.loop();

    TipoEvento ev;
    if (xQueueReceive(params->colaEventos, &ev, 0) == pdTRUE) {
      
      if (ev == EV_EMERGENCIA) {
        modoEmergencia = !modoEmergencia;

        if (modoEmergencia) {
          client.publish(topic_emergencia, "{\"estado\":\"EMERGENCY\"}");
          Serial.println("Publicado -> EMERGENCY");
        } else {
          client.publish(topic_emergencia, "{\"estado\":\"EMERGENCY_OFF\"}");
          Serial.println("Publicado  -> EMERGENCY_OFF");
          digitalWrite(LED_READY, HIGH); 
        }
      }
      else if (ev == EV_PALET_RECOGIDO) {
        client.publish(topic_palet, "{\"estado\":\"EMPTY\"}");
        digitalWrite(LED_PALET, HIGH);
        Serial.println("Publicado JSON -> topic lleno_vacio: EMPTY");
      }
    }

    if (modoEmergencia) {
      contadorParpadeo++;
      if (contadorParpadeo >= 10) {
        digitalWrite(LED_READY, !digitalRead(LED_READY));
        contadorParpadeo = 0;
      }
    }

    vTaskDelayUntil(&xLastWakeTime, xFrequency);
  }
}

// TAREA SENSOR ULTRASONIDOS
void tareaSensor(void *pvParameters) {
  DatosTareas* params = (DatosTareas*) pvParameters;
  
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = pdMS_TO_TICKS(100);
  
  EstadoSensor estadoActual = SENSOR_INACTIVO;

  for (;;) {
    EstadoSensor comando;
    if (xQueueReceive(params->colaControlSensor, &comando, 0) == pdTRUE) {
      estadoActual = comando;
    }

    if (estadoActual == SENSOR_ACTIVO) {
      digitalWrite(PIN_TRIG, LOW);
      delayMicroseconds(2);
      digitalWrite(PIN_TRIG, HIGH);
      delayMicroseconds(10);
      digitalWrite(PIN_TRIG, LOW);
      
      long duracion = pulseIn(PIN_ECHO, HIGH, 30000);
      float distancia = (duracion / 2.0) * 0.0343;

      if (distancia > 0 && distancia <= 5.0) {
        TipoEvento ev = EV_PALET_RECOGIDO;
        xQueueSend(params->colaEventos, &ev, portMAX_DELAY);
        estadoActual = SENSOR_INACTIVO;
      }
    }

    vTaskDelayUntil(&xLastWakeTime, xFrequency);
  }
}

void setup() {
  Serial.begin(115200);
  
  pinMode(LED_SENSOR1, OUTPUT);
  pinMode(LED_SENSOR2, OUTPUT);
  pinMode(LED_READY, OUTPUT);
  pinMode(LED_PALET, OUTPUT);
  pinMode(PIN_TRIG, OUTPUT);
  
  pinMode(PIN_ECHO, INPUT);
  pinMode(BTN_EMERGENCIA, INPUT_PULLUP);

  digitalWrite(LED_SENSOR1, HIGH);
  digitalWrite(LED_SENSOR2, HIGH);
  digitalWrite(LED_READY, HIGH);
  digitalWrite(LED_PALET, HIGH);

  static DatosTareas datosCompartidos;
  datosCompartidos.colaEventos = xQueueCreate(5, sizeof(TipoEvento));
  datosCompartidos.colaControlSensor = xQueueCreate(5, sizeof(EstadoSensor));

  ptrDatosGlobal = &datosCompartidos;

  attachInterrupt(digitalPinToInterrupt(BTN_EMERGENCIA), emergenciaISR, FALLING);

  xTaskCreate(tareaMQTT, "Conectividad MQTT", 4096, &datosCompartidos, 1, NULL);
  xTaskCreate(tareaSensor, "Control Ultrasonidos", 2048, &datosCompartidos, 1, NULL);
}

void loop() {
  
}