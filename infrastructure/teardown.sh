#!/bin/bash

if [ -f .env ]; then
  export $(cat .env | xargs)
fi

echo "Iniciando destrucción de $PROJECT_NAME..."
python start.py teardown