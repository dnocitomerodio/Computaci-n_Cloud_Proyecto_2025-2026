# Cloud Inventory & Notifications System

Proyecto de infraestructura Serverless en AWS para la gestión de inventario de una cafetería ("The Café").
Incluye ingesta de datos automática por CSV, API Serverless, Base de datos NoSQL y sistema de notificaciones por email.

## Estructura del Proyecto

/
├── infrastructure/ # Scripts de automatización (Python + Boto3)
│ ├── start.py # Script maestro (Deploy & Teardown)
│ ├── .env # Configuración (Emails, Región...)
│ └── ...
├── lambdas/ # Código fuente de las Funciones Lambda (Backend)
│ ├── load_inventory/
│ ├── get_inventory_api/
│ └── handle_contact/
├── web/ # Frontend (HTML, CSS, JS)
├── inventory/ # Archivos de datos (.csv) para pruebas
├── .aws/ # Configuración para credenciales de aws
│ ├── config # COnfiguración de la Regíon y Output
│ └── credentials # Credenciales que tienes que substituir
└── README.md # Este archivo

## Requisitos Previos

Python 3.11+ instalado.

AWS CLI configurado con credenciales activas (aws configure).

Librerías Python:

```powershell
pip install boto3 python-dotenv
```

## Configuración

Entra en la carpeta de infraestructura:

```powershell
cd infrastructure
```

Crea tu archivo de configuración:

Copia .env.sample a .env (o crea uno nuevo).

Edita .env y añade tu email real en MY_EMAIL para recibir las notificaciones del formulario de contacto.

## Despliegue (Deploy)

Este comando crea toda la infraestructura (DynamoDB, S3, Lambdas, API Gateway, SNS), despliega la web y carga los datos del inventario automáticamente.

```powershell
cd infrastructure
python start.py deploy
```

Al finalizar:

El script mostrará la URL de la Web y la URL de la API.

Recibirás un correo de AWS Notifications. ¡Debes confirmar la suscripción haciendo clic en el enlace del email!

Al abrir la web, verás el inventario cargado automáticamente desde inventory/inventory.csv.

## Limpieza (Teardown)

Ejecuta este comando al terminar para borrar todos los recursos (Buckets, Tablas, Funciones) y evitar costes o penalizaciones en AWS.

```powershell
cd infrastructure
python start.py teardown
```
