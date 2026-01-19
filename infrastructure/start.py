import boto3
import json
import time
import os
import zipfile
import tempfile
import sys
import argparse
from dotenv import load_dotenv

try:
    load_dotenv()
except:
    pass

REGION = os.getenv('AWS_REGION', 'us-east-1')
PROJECT_NAME = os.getenv('PROJECT_NAME', 'practica-cloud-2026')
MY_EMAIL = os.getenv('MY_EMAIL', '')
TABLE_NAME = os.getenv('TABLE_NAME', 'Inventory')

SNS_TOPIC_NAME = 'CafeContactTopic'

s3 = boto3.client('s3', region_name=REGION)
dynamodb = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
apigateway = boto3.client('apigatewayv2', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)

def get_lab_role_arn():
    try:
        return iam.get_role(RoleName='LabRole')['Role']['Arn']
    except:
        print("ERROR: No se encontró 'LabRole'.")
        sys.exit(1)

def get_account_id():
    return sts.get_caller_identity()['Account']


def deploy_infrastructure():
    print(f"\n--- INICIANDO DESPLIEGUE ({PROJECT_NAME}) ---")
    
    bucket_ingest = f'{PROJECT_NAME}-ingest-{int(time.time())}'
    bucket_web = f'{PROJECT_NAME}-web-{int(time.time())}'
    role_arn = get_lab_role_arn()

    print(f"1. DynamoDB: {TABLE_NAME}")
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{'AttributeName': 'Store', 'KeyType': 'HASH'}, {'AttributeName': 'Item', 'KeyType': 'RANGE'}],
            AttributeDefinitions=[{'AttributeName': 'Store', 'AttributeType': 'S'}, {'AttributeName': 'Item', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        dynamodb.get_waiter('table_exists').wait(TableName=TABLE_NAME)
    except dynamodb.exceptions.ResourceInUseException:
        print("   (La tabla ya existía)")

    for b in [bucket_ingest, bucket_web]:
        print(f"2. Creando Bucket: {b}")
        if REGION == 'us-east-1': s3.create_bucket(Bucket=b)
        else: s3.create_bucket(Bucket=b, CreateBucketConfiguration={'LocationConstraint': REGION})
        try: s3.delete_public_access_block(Bucket=b)
        except: pass

    print("3. Configurando SNS...")
    topic_res = sns.create_topic(Name=SNS_TOPIC_NAME)
    if MY_EMAIL and '@' in MY_EMAIL:
        sns.subscribe(TopicArn=topic_res['TopicArn'], Protocol='email', Endpoint=MY_EMAIL)
        print(f"   IMPORTANTE: Confirma el email enviado a {MY_EMAIL}")

    print("4. Desplegando Lambdas...")
    lambdas = ['load_inventory', 'get_inventory_api', 'handle_contact']
    env_vars = {'TABLE_NAME': TABLE_NAME, 'TOPIC_ARN': topic_res['TopicArn']}
    
    for l_name in lambdas:
        zip_name = f"{l_name}.zip"
        zip_lambda(os.path.join('..', 'lambdas', l_name), zip_name)
        
        with open(zip_name, 'rb') as f: code = f.read()
        try:
            lambda_client.create_function(
                FunctionName=l_name, Runtime='python3.11', Role=role_arn, Handler='lambda_function.lambda_handler',
                Code={'ZipFile': code}, Environment={'Variables': env_vars}, Timeout=30
            )
        except lambda_client.exceptions.ResourceConflictException:
            lambda_client.update_function_code(FunctionName=l_name, ZipFile=code)
            time.sleep(2)
            lambda_client.update_function_configuration(FunctionName=l_name, Environment={'Variables': env_vars})
        
        try: os.remove(zip_name)
        except: pass

    print("5. Creando API Gateway...")
    api = apigateway.create_api(Name='CafeAPI_v2', ProtocolType='HTTP', CorsConfiguration={'AllowOrigins': ['*'], 'AllowMethods': ['GET', 'POST', 'OPTIONS'], 'AllowHeaders': ['content-type']})
    api_id = api['ApiId']
    apigateway.create_stage(ApiId=api_id, StageName='$default', AutoDeploy=True)
    setup_api_routes(api_id, lambdas)
    
    print("6. Conectando piezas finales...")
    setup_s3_notification(bucket_ingest, 'load_inventory')
    
    s3.put_bucket_website(Bucket=bucket_web, WebsiteConfiguration={'IndexDocument': {'Suffix': 'index.html'}})
    policy = {"Version": "2012-10-17","Statement": [{"Sid": "PublicRead","Effect": "Allow","Principal": "*","Action": "s3:GetObject","Resource": f"arn:aws:s3:::{bucket_web}/*"}]}
    s3.put_bucket_policy(Bucket=bucket_web, Policy=json.dumps(policy))
    
    upload_website(bucket_web, api['ApiEndpoint'])

    upload_initial_data(bucket_ingest)

    print(f"\n DESPLIEGUE COMPLETADO")
    print(f"WEB: http://{bucket_web}.s3-website-{REGION}.amazonaws.com/")


def teardown_infrastructure():
    print(f"\n--- INICIANDO DESTRUCCIÓN (TEARDOWN) ---")
    
    print("1. Buscando Buckets S3...")
    buckets = s3.list_buckets()['Buckets']
    for b in buckets:
        if PROJECT_NAME in b['Name']:
            print(f"   -> Vaciando y borrando {b['Name']}...")
            try:
                objs = s3.list_objects_v2(Bucket=b['Name'])
                if 'Contents' in objs:
                    for obj in objs['Contents']:
                        s3.delete_object(Bucket=b['Name'], Key=obj['Key'])
                s3.delete_bucket(Bucket=b['Name'])
            except Exception as e:
                print(f"Error borrando bucket: {e}")

    print(f"2. Borrando tabla {TABLE_NAME}...")
    try: dynamodb.delete_table(TableName=TABLE_NAME)
    except: pass

    print("3. Borrando APIs...")
    try:
        apis = apigateway.get_apis()['Items']
        for api in apis:
            if api['Name'] == 'CafeAPI_v2':
                apigateway.delete_api(ApiId=api['ApiId'])
    except: pass

    print("4. Borrando Lambdas...")
    lambdas = ['load_inventory', 'get_inventory_api', 'handle_contact']
    for l in lambdas:
        try: lambda_client.delete_function(FunctionName=l)
        except: pass

    print("5. Borrando Topic SNS...")
    topics = sns.list_topics()['Topics']
    for t in topics:
        if SNS_TOPIC_NAME in t['TopicArn']:
            sns.delete_topic(TopicArn=t['TopicArn'])

    print("\n TEARDOWN COMPLETADO. Todo limpio.")

def zip_lambda(path, output):
    if not os.path.exists(os.path.join(path, "lambda_function.py")): return
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(path, "lambda_function.py"), arcname="lambda_function.py")

def setup_s3_notification(bucket, func):
    try:
        arn = lambda_client.get_function(FunctionName=func)['Configuration']['FunctionArn']
        lambda_client.add_permission(FunctionName=func, StatementId='s3-trig-'+str(int(time.time())), Action='lambda:InvokeFunction', Principal='s3.amazonaws.com', SourceArn=f"arn:aws:s3:::{bucket}")
        s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration={'LambdaFunctionConfigurations': [{'LambdaFunctionArn': arn, 'Events': ['s3:ObjectCreated:*'], 'Filter': {'Key': {'FilterRules': [{'Name': 'suffix', 'Value': '.csv'}]}}}]})
    except: pass

def setup_api_routes(api_id, funcs):
    inv_arn = lambda_client.get_function(FunctionName='get_inventory_api')['Configuration']['FunctionArn']
    cont_arn = lambda_client.get_function(FunctionName='handle_contact')['Configuration']['FunctionArn']
    
    int_inv = apigateway.create_integration(ApiId=api_id, IntegrationType='AWS_PROXY', IntegrationUri=inv_arn, PayloadFormatVersion='2.0')['IntegrationId']
    int_cont = apigateway.create_integration(ApiId=api_id, IntegrationType='AWS_PROXY', IntegrationUri=cont_arn, PayloadFormatVersion='2.0')['IntegrationId']
    
    apigateway.create_route(ApiId=api_id, RouteKey='GET /items', Target=f'integrations/{int_inv}')
    apigateway.create_route(ApiId=api_id, RouteKey='GET /items/{store}', Target=f'integrations/{int_inv}')
    apigateway.create_route(ApiId=api_id, RouteKey='POST /contact', Target=f'integrations/{int_cont}')
    
    for f in funcs:
        try: lambda_client.add_permission(FunctionName=f, StatementId=f'api-{api_id}-{f}', Action='lambda:InvokeFunction', Principal='apigateway.amazonaws.com', SourceArn=f"arn:aws:execute-api:{REGION}:{get_account_id()}:{api_id}/*/*")
        except: pass

def upload_website(bucket, api_url):
    web_path = os.path.join('..', 'web')
    index_path = os.path.join(web_path, 'index.html')
    if not os.path.exists(index_path): return
    with open(index_path, 'r', encoding='utf-8') as f: html = f.read().replace("REPLACE_ME_WITH_YOUR_INVOKE_URL", api_url)
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.html') as tmp:
        tmp.write(html)
        tmp_name = tmp.name
    s3.upload_file(tmp_name, bucket, 'index.html', ExtraArgs={'ContentType': 'text/html'})
    try: os.unlink(tmp_name)
    except: pass
    
    for root, dirs, files in os.walk(web_path):
        for file in files:
            if file == 'index.html': continue
            ctype = 'text/plain'
            if file.endswith('.css'): ctype = 'text/css'
            if file.endswith('.png'): ctype = 'image/png'
            s3.upload_file(os.path.join(root, file), bucket, os.path.relpath(os.path.join(root, file), web_path).replace("\\", "/"), ExtraArgs={'ContentType': ctype})

def upload_initial_data(bucket_name):
    print("7. Subiendo datos iniciales (Inventory)...")
    csv_path = os.path.join('..', 'inventory', 'inventory.csv')
    if os.path.exists(csv_path):
        s3.upload_file(csv_path, bucket_name, 'inventory.csv')
        print(f"   -> {csv_path} subido a {bucket_name}. Esto activará la Lambda.")
    else:
        print(f"   No se encontró {csv_path}. Recuerda subirlo manualmente.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['deploy', 'teardown'], help="Acción a realizar")
    args = parser.parse_args()

    if args.action == 'deploy':
        deploy_infrastructure()
    elif args.action == 'teardown':
        teardown_infrastructure()