#!/bin/bash

if [ -f .env ]; then
  export $(cat .env | xargs)
else
  echo "No se encontró .env, usando valores por defecto..."
fi

pip install python-dotenv boto3 -q > /dev/null 2>&1

echo "Iniciando despliegue de $PROJECT_NAME..."
python start.py deploy