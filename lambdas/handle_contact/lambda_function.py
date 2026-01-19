import json
import boto3
import os

sns_client = boto3.client('sns')
TOPIC_ARN = os.environ.get('TOPIC_ARN')

def lambda_handler(event, context):
    print("Recibiendo solicitud de contacto...")
    try:
        body = json.loads(event.get('body', '{}'))
        
        message = body.get('message', 'Sin mensaje')
        email = body.get('email', 'Anónimo')
        name = body.get('firstName', 'Cliente')

        full_message = f"Nuevo mensaje de {name} ({email}):\n\n{message}"

        print(f"Enviando mensaje a SNS: {TOPIC_ARN}")
        response = sns_client.publish(
            TopicArn=TOPIC_ARN,
            Message=full_message,
            Subject=f"Nuevo contacto Web: {name}"
        )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST'
            },
            'body': json.dumps({'status': 'Message sent!'})
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }