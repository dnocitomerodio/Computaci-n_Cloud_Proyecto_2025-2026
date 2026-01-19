import json
import boto3
import os
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Inventory')
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET"
    }
    
    try:
        path_parameters = event.get('pathParameters') or {}
        store_filter = path_parameters.get('store')

        if store_filter:
            response = table.query(
                KeyConditionExpression=Key('Store').eq(store_filter)
            )
        else:
            response = table.scan()

        items = response.get('Items', [])
        
        for i in items:
            if 'Count' in i:
                i['Count'] = int(i['Count'])

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(items)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }