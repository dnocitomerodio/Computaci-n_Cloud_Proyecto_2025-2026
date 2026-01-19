import boto3

BUCKET_NAME = 'practica-cloud-2026-ingest-1768469447'
FILE_NAME = 'inventory.csv'

s3 = boto3.client('s3')

print(f"Subiendo {FILE_NAME} a {BUCKET_NAME}...")
try:
    s3.upload_file(FILE_NAME, BUCKET_NAME, FILE_NAME)
    print("¡Archivo subido con éxito!")
except Exception as e:
    print(f"Error: {e}")