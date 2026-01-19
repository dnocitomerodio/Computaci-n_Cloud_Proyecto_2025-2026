import boto3
import csv
import os

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

TABLE_NAME = os.environ.get('TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

def clear_table():
    """
    Escanea toda la tabla y borra los elementos uno a uno.
    Nota: Esto no es eficiente para tablas gigantes, pero es perfecto para este laboratorio.
    """
    print("Iniciando limpieza de la tabla...")
    scan = table.scan()
    items = scan.get('Items', [])
    
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(
                Key={
                    'Store': item['Store'],
                    'Item': item['Item']
                }
            )
    print(f"Se han borrado {len(items)} elementos antiguos.")

def lambda_handler(event, context):
    try:
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']
        
        print(f"Procesando archivo: {file_key} desde bucket: {bucket_name}")

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        lines = response['Body'].read().decode('utf-8').splitlines()
        
        clear_table()

        csv_reader = csv.DictReader(lines)
        
        with table.batch_writer() as batch:
            count = 0
            for row in csv_reader:
                if 'Count' in row:
                    row['Count'] = int(row['Count'])
                
                batch.put_item(Item=row)
                count += 1
                
        print(f"Exito! Se insertaron {count} nuevos elementos.")
        return {'statusCode': 200, 'body': f'Procesados {count} items.'}

    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'body': str(e)}